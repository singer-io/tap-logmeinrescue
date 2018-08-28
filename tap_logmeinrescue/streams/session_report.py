from tap_logmeinrescue.streams.base import BaseLogMeInRescueReportStream


class SessionReportStream(BaseLogMeInRescueReportStream):
    TABLE = 'session_report'
    KEY_PROPERTIES = ['session_id']
    API_METHOD = 'GET'
    REPORT_AREA = 0
    REQUIRES = ['technicians']
