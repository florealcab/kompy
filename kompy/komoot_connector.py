import json
import logging
import re
from typing import Optional, List

import dateutil.parser as parser
import requests

from kompy.constants.activities import SupportedActivities
from kompy.constants.privacy_status import PrivacyStatus
from kompy.constants.query_parameters import TourQueryParameters
from kompy.constants.tour_constants import TourSort, TourSortField, TourTypes
from kompy.constants.urls import KomootUrl
from kompy.errors.initialisation_errors import NotEmailError
from kompy.errors.privacy_errors import PrivacyError


class KomootConnector:

    def __init__(
        self,
        email: str,
        password: str,
    ):
        """
        Connector to Komoot API.
        :param email: email address used to log in to Komoot
        :param password: password used to log in to Komoot
        """
        if not re.match(
            pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b',
            string=email,
        ):
            raise NotEmailError(email)
        else:
            self.email = email
        self.password = password
        try:
            response = requests.get(
                url=KomootUrl.USER_LOGIN_URL.format(email_address=self.email),
                auth=(self.email, self.password),
            )
            if response.status_code == 403:
                raise ConnectionError(
                    'Connection to Komoot API failed. Please check your credentials.'
                )
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                'Connection to Komoot API failed. Please check your internet connection.'
            )
        self.token = response.json()['password']
        self.logged_username = json.loads(response.content.decode('utf-8'))['username']

    def get_tours(
        self,
        user_identifier: Optional[str] = None,
        page: Optional[int] = None,
        status: Optional[str] = PrivacyStatus.PUBLIC,
        tour_type: Optional[str] = None,
        only_unlocked: Optional[bool] = False,
        center: Optional[str] = None,
        max_distance: Optional[int] = None,
        sport_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tour_name: Optional[str] = None,
        sort: Optional[str] = None,
        sort_field: Optional[str] = None,
    ):
        """
        Get a list of tours.
        :param user_identifier: The user identifier, if not provided, the logged in user is used
        :param page: The page to retrieve, if not provided, the first page is used
        :param status: The privacy status of the tour, if not provided, only public tours are returned
        :param tour_type: The tour type, if not provided, all tours are returned
        :param only_unlocked: Whether to only return unlocked tours, if not provided, all tours are returned
        :param center: The center of the search area, if not provided, all tours are returned
        :param max_distance: The maximum distance to the center, if not provided, all tours are returned
        :param sport_types: The sport types to filter by, if not provided, all tours are returned
        :param start_date: The start date to filter by, if not provided, all tours are returned
        :param end_date: The end date to filter by, if not provided, all tours are returned
        :param tour_name: The tour name to filter by, if not provided, all tours are returned
        :param sort: The sort direction, if not provided, all tours are returned
        :param sort_field: The field to sort by, if not provided, all tours are returned
        :return: A list of tours
        """
        if user_identifier is None:
            logging.warning(f'No user identifier provided, using the currently logged user: {self.logged_username}')
            user_identifier = self.logged_username
        if status is None:
            status = PrivacyStatus.PUBLIC
        if status is not PrivacyStatus.PUBLIC and self.logged_username != user_identifier:
            raise PrivacyError(user_identifier)
        if tour_type is not None and tour_type not in [TourTypes.TOUR_PLANNED, TourTypes.TOUR_RECORDED]:
            raise ValueError(f'Invalid tour type provided: {tour_type}. Please provide a valid tour type.')
        if center is not None:
            if not re.match(
                pattern=r'^[-+]?\d{1,2}(\.\d+)?,\s*[-+]?\d{1,3}(\.\d+)?$',
                string=center,
            ):
                raise ValueError(
                    f'Invalid center provided: {center}. '
                    f'Please provide a valid center in the format "lat, lon" (e.g. "52.520008, 13.404954").'
                )
        if max_distance is None and center is not None:
            raise ValueError('Max distance must be provided if center is provided.')
        if max_distance is not None and center is None:
            logging.warning('Max distance provided but no center, ignoring max distance.')
        if sport_types is not None:
            if not isinstance(sport_types, list):
                raise TypeError(f'Invalid sport types provided: {sport_types}. Please provide a list of strings.')
            for sport_type in sport_types:
                if not isinstance(sport_type, str):
                    raise TypeError(f'Invalid sport type provided: {sport_type}. Please provide a string.')
                if sport_type not in SupportedActivities.list_all():
                    raise ValueError(f'Invalid sport type provided: {sport_type}. Please provide a valid sport type.')
        if start_date is not None:
            start_date = parser.parse(start_date)
        if end_date is not None:
            end_date = parser.parse(end_date)
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError(f'Start date ({start_date}) must be before end date ({end_date}).')
        if sort is not None and sort not in [TourSort.ASCENDING, TourSort.DESCENDING]:
            raise ValueError(f'Invalid sort provided: {sort}. Please provide a valid sort (can be '
                             f'{TourSort.ASCENDING} or {TourSort.DESCENDING}')
        if sort_field is not None and sort_field not in TourSortField.list_all():
            raise ValueError(f'Invalid sort field provided: {sort_field}. Please provide a valid sort field.')
        if not sort_field:
            logging.warning('No sort field provided, using default sort field: date')
        if sort_field == TourSortField.PROXIMITY and center is None:
            raise ValueError('Sort field proximity requires a center to be provided.')

        query_parameters = TourQueryParameters.construct_tour_query(
            limit=TourQueryParameters.LIMIT,
            page=page,
            status=status,
            tour_type=tour_type,
            only_unlocked=only_unlocked,
            center=center,
            max_distance=max_distance,
            sport_types=sport_types,
            start_date=start_date,
            end_date=end_date,
            name=tour_name,
            sort_direction=sort,
            sort_field=sort_field,
        )