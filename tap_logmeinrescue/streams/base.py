from datetime import datetime, timedelta
import funcy
import pytz
import singer
import xml.etree.ElementTree as ET

from dateutil.parser import parse

from tap_framework.streams import BaseStream
from tap_framework.config import get_config_start_date
from tap_logmeinrescue.state import get_last_record_value_for_table, \
    incorporate, save_state

from tap_logmeinrescue.logger import LOGGER

class BaseLogMeInRescueStream(BaseStream):

    def convert_key(self, k):
        # replace disallowed characters used in keys
        k = k.replace('–', '')
        k = k.replace('/', '_')

        # replace whitespace and downcase everything
        return k.replace(' ', '_').lower()

    def convert_keys(self, d):
        to_return = {}

        for k, v in d.items():
            to_return[self.convert_key(k)] = v

        return to_return

    def transform_record(self, record):
        converted = self.convert_keys(record)

        return super().transform_record(converted)


class BaseLogMeInRescueReportStream(BaseLogMeInRescueStream):

    REPORT_AREA = None

    def get_url(self):
        return 'https://secure.logmeinrescue.com/API/getReport_v2.aspx'

    def generate_catalog(self, technician_id):
        schema = self.get_schema(technician_id)
        mdata = singer.metadata.new()

        mdata = singer.metadata.write(
            mdata,
            (),
            'inclusion',
            'available'
        )

        for field_name, field_schema in schema.get('properties').items():
            inclusion = 'available'

            if field_name in self.KEY_PROPERTIES:
                inclusion = 'automatic'

            mdata = singer.metadata.write(
                mdata,
                ('properties', field_name),
                'inclusion',
                inclusion
            )

        return [{
            'tap_stream_id': self.TABLE,
            'stream': self.TABLE,
            'key_properties': self.KEY_PROPERTIES,
            'schema': schema,
            'metadata': singer.metadata.to_list(mdata)
        }]

    def get_schema(self, technician_id):
        custom_field_schema = self.header_to_string_schema(self.get_headers(technician_id))

        schema = self.load_schema_by_name(self.TABLE)
        schema['properties'] = funcy.merge(
            custom_field_schema,
            schema['properties'])

        return schema


    def header_to_string_schema(self, header):
        return {self.convert_key(h): {"type": ["string", "null"]} for h in header}


    def get_headers(self, technician_id):
        start_date = get_config_start_date(self.config)
        end_date = start_date + timedelta(days=7)
        parsed_response = self.execute_request(technician_id, start_date, end_date)
        return parsed_response['headers']


    def execute_request(self, parent_id, start_date, end_date):
        # Sets the Report Type so that we generate a specific type of report
        resp = self.client.make_request(
            'https://secure.logmeinrescue.com/API/setReportArea_v8.aspx',
            'POST',
            params={'area': self.REPORT_AREA})
        status = resp.split("\n\n", 1)[0]
        if status != "OK":
            raise Exception("Error with setReportArea request: {}".format(status))

        LOGGER.info(
            ('Fetching session report for technician {}'
             'from {} to {}')
            .format(parent_id, start_date, end_date))

        # Sets the start and end date on the report to be generated
        report_dates = {'bdate': start_date.strftime('%-m/%-d/%Y %H:%M:%S'),
                        'edate': end_date.strftime('%-m/%-d/%Y %H:%M:%S')}
        resp = self.client.make_request(
            'https://secure.logmeinrescue.com/API/setReportDate_v2.aspx',  # noqa
            'POST',
            params=report_dates)
        status = resp.split("\n\n", 1)[0]
        if status != "OK":
            raise Exception("Error with setReportDate request: {}".format(status))

        # Set the report output to XML so that it can be
        # parsed. Text output is buggy as it does not properly
        # escape the field delimeter.
        output_type = 'XML'
        self.client.make_request(
            'https://secure.logmeinrescue.com/API/setOutput.aspx',
            'POST',
            params={'output': output_type})
        status = resp.split("\n\n", 1)[0]
        if status != "OK":
            raise Exception("Error with setOutput request: {}".format(status))

        # Calls the generate report endpoint
        report_params = {'node': parent_id,
                         'nodetype': 'NODE'}
        raw_response = self.client.make_request(
            self.get_url(),
            'GET',
            params=report_params)

        # The response will contain a status followed by two newlines
        status, data = raw_response.split("\n\n", 1)

        if status != "OK":
            msg = "Error retrieving report: {}\nReport Params: {}\nReport Dates: {}".format(status, report_params, report_dates)
            raise Exception(msg)

        return self.parse_data(data)


    def sync_data(self, parent_ids):
        table = self.TABLE

        self.write_schema()

        start_date = get_last_record_value_for_table(
            self.state, table, 'start_date')
        technician_id = get_last_record_value_for_table(
            self.state, table, 'technician_id')

        if start_date is None:
            start_date = get_config_start_date(self.config)
        else:
            start_date = parse(start_date)

        if technician_id is None:
            technician_id = 0

        end_date = start_date + timedelta(days=7)

        while start_date < datetime.now(tz=pytz.UTC):
            for index, parent_id in enumerate(parent_ids):
                if parent_id < technician_id:
                    continue

                LOGGER.info(
                    ('Fetching session report for technician {} ({}/{}) '
                     'from {} to {}')
                    .format(parent_id, index + 1, len(parent_ids), start_date, end_date))

                parsed_response = self.execute_request(parent_id, start_date, end_date)

                with singer.metrics.record_counter(endpoint=table) as ctr:
                    singer.write_records(table, parsed_response['rows'])

                    ctr.increment(amount=len(parsed_response['rows']))

                self.state = incorporate(
                    self.state, table, 'technician_id', parent_id)
                self.state = incorporate(
                    self.state, table, 'start_date', start_date)
                self.state = save_state(self.state)

            start_date = end_date
            end_date = start_date + timedelta(days=7)
            technician_id = 0

            self.state = incorporate(
                self.state, table, 'start_date', start_date)
            self.state = incorporate(
                self.state, table, 'technician_id', technician_id,
                force=True)
            self.state = save_state(self.state)


    def parse_data(self, data):
        tree = ET.fromstring(data)
        headers = tree.find('header')

        to_return = {}
        rows = []

        for row in tree.findall('./data/row'):
            to_add = {}
            for field in row.findall('field'):
                header_id = field.attrib['id']
                attrib_finder = "field[@id='{}']".format(header_id)
                header_text = headers.find(attrib_finder).text
                to_add[header_text] = field.text

            rows.append(self.transform_record(to_add))

        to_return['headers'] = [self.convert_key(e.text) for e in headers.findall('./field')]
        to_return['rows'] = rows
        return to_return
