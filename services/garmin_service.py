"""Garmin service for handling authentication and activity uploads.

Login apenas por token salvo (garminconnect 0.3.x). A senha e o código MFA do
Garmin nunca passam por aqui: são digitados uma vez em `scripts/login_garmin.py`,
que grava só o token.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from datetime import datetime
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
    GarminConnectConnectionError
)

logging.getLogger("garminconnect").setLevel(logging.CRITICAL)


class GarminTokenInvalid(RuntimeError):
    """Não há token válido. É preciso rodar `python scripts/login_garmin.py`."""


def is_rate_limited(error: BaseException) -> bool:
    """429: o Garmin pediu para parar. Insistir só estende o bloqueio."""
    if isinstance(error, GarminConnectTooManyRequestsError):
        return True
    text = str(error).lower()
    return "429" in text or "too many" in text


class GarminService:
    """Service for interacting with Garmin Connect."""

    def __init__(self, tokenstore: Union[str, Path]):
        """Initialize GarminService with the token folder.

        Args:
            tokenstore: Pasta com o token gerado por scripts/login_garmin.py
        """
        self.tokenstore = Path(tokenstore).expanduser()
        self.client: Garmin = Garmin()
        self.logger = logging.getLogger(__name__)
        self._authenticated = False

    def authenticate(self) -> None:
        """Authenticate with Garmin Connect using the saved token.

        Raises:
            GarminTokenInvalid: Sem token, ou token expirado/revogado
            GarminConnectTooManyRequestsError: Rate limit exceeded
        """
        self.logger.info("Logging in to Garmin Connect (saved token)...")
        if not self.tokenstore.exists():
            raise GarminTokenInvalid(
                f"Nenhum token do Garmin em '{self.tokenstore}'. "
                "Rode `python scripts/login_garmin.py` uma vez neste PC."
            )
        try:
            self.client.login(str(self.tokenstore))
            self._authenticated = True
            self.logger.info("Successfully authenticated with Garmin Connect")
        except GarminConnectTooManyRequestsError:
            self.logger.error("Garmin limitou as requisições deste IP (429). Tente em algumas horas.")
            raise
        except (GarminConnectAuthenticationError, GarminConnectConnectionError) as e:
            raise GarminTokenInvalid(
                "O token do Garmin expirou ou foi revogado "
                f"({e}). Rode `python scripts/login_garmin.py` de novo."
            ) from e

    def upload_activity(self, fit_file_path: str) -> Any:
        """Upload a .fit file to Garmin Connect.

        Args:
            fit_file_path: Path to the FIT file to upload

        Returns:
            Upload response from Garmin Connect or success dict if 409 Conflict (duplicate)

        Raises:
            RuntimeError: If not authenticated or upload fails (other than 409)
        """
        if not self._authenticated:
            raise RuntimeError("Must authenticate before uploading activities")

        self.logger.info(f"Uploading {fit_file_path} to Garmin Connect...")

        try:
            response = self.client.upload_activity(fit_file_path)
            self.logger.info("Upload successful")
            self.logger.debug(f"Upload response: {response}")
            return response
        except Exception as e:
            error_str = str(e)
            
            # Handle 409 Conflict gracefully (activity already exists)
            if "409" in error_str or "Conflict" in error_str:
                self.logger.info("⚠ Activity already exists on Garmin Connect (409 Conflict)")
                self.logger.info("Treating as success - no duplicate upload needed")
                return {"status": "skipped", "message": "Activity already exists on Garmin Connect"}
            
            if is_rate_limited(e):
                raise
            self.logger.exception(f"Failed to upload activity: {e}")
            raise RuntimeError(f"Upload failed: {e}") from e

    def is_authenticated(self) -> bool:
        """Check if the service is authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        return self._authenticated

    def check_duplicate_activity(
        self,
        activity_date: datetime,
        activity_name: Optional[str] = None,
        threshold_hours: int = 2
    ) -> bool:
        """Check if an activity already exists on Garmin Connect.

        Uses a time window approach: if an activity exists within
        threshold_hours of the given activity_date, it's considered a duplicate.

        Args:
            activity_date: Date/time when the activity occurred
            activity_name: Optional activity name for additional matching
            threshold_hours: Time window in hours (default: 2)

        Returns:
            True if duplicate found, False otherwise

        Raises:
            RuntimeError: If not authenticated
        """
        if not self._authenticated:
            raise RuntimeError("Must authenticate before checking activities")

        self.logger.info(
            f"Checking for duplicate activity around {activity_date} "
            f"(±{threshold_hours}h window)"
        )

        try:
            # Get activities for the date
            date_str = activity_date.strftime('%Y-%m-%d')
            activities = self.client.get_activities_by_date(date_str, date_str)

            if not activities:
                self.logger.info("No activities found on this date")
                return False

            self.logger.info(f"Found {len(activities)} activities on {date_str}")

            # Check each activity
            for activity in activities:
                try:
                    # Parse activity start time
                    start_time_str = activity.get('startTimeLocal', activity.get('startTime'))
                    if not start_time_str:
                        continue

                    # Handle different time formats
                    start_time_str = start_time_str.replace('Z', '+00:00')
                    activity_start = datetime.fromisoformat(start_time_str)

                    # Calculate time difference in hours
                    time_diff = abs((activity_start - activity_date).total_seconds() / 3600)

                    if time_diff <= threshold_hours:
                        self.logger.info(
                            f"Found potential duplicate: '{activity.get('activityName')}' "
                            f"at {activity_start} (Δ{time_diff:.1f}h)"
                        )

                        # Additional name matching if provided
                        if activity_name:
                            garmin_name = activity.get('activityName', '').lower()
                            if activity_name.lower() in garmin_name or garmin_name in activity_name.lower():
                                self.logger.info("✓ Activity name matches - confirmed duplicate")
                                return True
                            else:
                                self.logger.info("✗ Activity name doesn't match, checking next...")
                                continue
                        else:
                            # No name provided, time match is sufficient
                            return True

                except Exception as e:
                    self.logger.warning(f"Error parsing activity: {e}")
                    continue

            self.logger.info("No duplicate found")
            return False

        except Exception as e:
            if is_rate_limited(e):
                raise
            self.logger.warning(f"Error checking for duplicates: {e}")
            # Don't block upload if duplicate check fails
            return False
