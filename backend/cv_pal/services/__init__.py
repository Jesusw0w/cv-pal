"""Business logic, independent of the HTTP layer.

Services never raise ``HTTPException`` and never touch request or response objects;
they raise domain errors from :mod:`cv_pal.exceptions`, which the API edge translates.
"""
