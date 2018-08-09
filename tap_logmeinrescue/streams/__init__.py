from .session_report import SessionReportStream
from .technicians import TechniciansStream
from .technician_survey_report import TechnicianSurveyReportStream
from .transferred_sessions_extended_report \
    import TransferredSessionsExtendedReportStream

AVAILABLE_STREAMS = [
    SessionReportStream,
    TechniciansStream,
    TechnicianSurveyReportStream,
    TransferredSessionsExtendedReportStream,
]
