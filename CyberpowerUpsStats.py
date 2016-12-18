import os
import sys
import configparser
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from urllib.request import urlopen
import json
import time

__author__ = 'Matthew Carey'

class CyberpowerUpsStats():

    def __init__(self):

        self.config = configManager()
        self.ups_address = self.config.ups_address
        self.ups_port = self.config.ups_port
        self.output = self.config.output
        self.delay = self.config.delay

        self.influx_client = InfluxDBClient(self.config.influx_address, self.config.influx_port, database=self.config.influx_database)

    def write_influx_data(self, json_data):
        """
        Writes the provided JSON to the database
        :param json_data:
        :return:
        """
        if self.output:
            print(json_data)
        try:
            self.influx_client.write_points(json_data)
        except InfluxDBClientError as e:
            if e.code == 404:
                print('Database {} Does Not Exist.  Attempting To Create')
                # TODO Grab exception here
                self.influx_client.create_database(self.config.influx_database)

    def get_ups_data(self):
        """
        Quick and dirty way to get UPS data from Power Panel.  ppbe.js returns dirty JSON with the data we want.
        We have to strip the invalid JSON and then proceed with parsing it.
        :return:
        """

        uri = 'http://{}:{}/agent/ppbe.js/init_status.js'.format(self.ups_address, self.ups_port)
        raw_data = urlopen(uri).read().decode('utf-8')

        # Cleanup response to make it valid JSON
        result = raw_data.strip("var ppbeJsObj=")
        result = result.strip("\n")
        result = result[:-1]

        try:
            json_out = json.loads(result)
        except json.decoder.JSONDecodeError as e:
            print('ERROR: Problem decoding the response JSON')
            return

        self._process_ups_data(json_out)


    def _process_ups_data(self, ups_data):

        # Utility Data
        utility_json = [
            {
                'measurement': 'utility_data',
                'fields' : {
                    'state': ups_data['status']['utility']['state'],
                    'state_warning': ups_data['status']['utility']['stateWarning'],
                    'voltage': ups_data['status']['utility']['voltage'],
                },
                'tags': {
                    'ups': 'UPS1'
                }
            }
        ]

        output_json = [
            {
                'measurement': 'output_data',
                'fields' : {
                    'state': ups_data['status']['output']['state'],
                    'state_warning': ups_data['status']['output']['stateWarning'],
                    'voltage': ups_data['status']['output']['voltage'],
                    'load': ups_data['status']['output']['load'],
                    'watts': ups_data['status']['output']['watt'],
                    'outputLoadWarning': ups_data['status']['output']['outputLoadWarning'],

                },
                'tags': {
                    'ups': 'UPS1'
                }
            }
        ]

        battery_json = [
            {
                'measurement': 'output_data',
                'fields' : {
                    'state': ups_data['status']['battery']['state'],
                    'state_warning': ups_data['status']['battery']['stateWarning'],
                    'voltage': ups_data['status']['battery']['voltage'],
                    'capacity': ups_data['status']['battery']['capacity'],
                    'runtimeHour': ups_data['status']['battery']['runtimeHour'],
                    'runtimeMinute': ups_data['status']['battery']['runtimeMinute'],

                },
                'tags': {
                    'ups': 'UPS1'
                }
            }
        ]

        self.write_influx_data(utility_json)
        self.write_influx_data(output_json)
        self.write_influx_data(battery_json)

    def run(self):
        while True:
            self.get_ups_data()
            time.sleep(self.delay)


class configManager():

    def __init__(self):
        print('Loading Configuration File')
        config_file = os.path.join(os.getcwd(), 'config.ini')
        if os.path.isfile(config_file):
            self.config = configparser.ConfigParser()
            self.config.read(config_file)
        else:
            print('ERROR: Unable To Load Config File')
            sys.exit(1)

        self._load_config_values()
        print('Configuration Successfully Loaded')

    def _load_config_values(self):

        # General
        self.delay = self.config['GENERAL'].getint('Delay', fallback=2)
        self.output = self.config['GENERAL'].getboolean('Output', fallback=True)

        # InfluxDB
        self.influx_address = self.config['INFLUXDB']['Address']
        self.influx_port = self.config['INFLUXDB'].getint('Port', fallback=8086)
        self.influx_database = self.config['INFLUXDB'].get('Database', fallback='plex_data')

        # UPS
        self.ups_address = self.config['UPS']['Address']
        self.ups_port = self.config['UPS'].get('Port', fallback=3052)

def main():

    ups_stats = CyberpowerUpsStats()
    ups_stats.run()



if __name__ == '__main__':
    main()