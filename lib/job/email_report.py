#!/usr/bin/env python3

# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os
from datetime import datetime

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../')

from lib.db import DB
from lib.global_config import GlobalConfig
from lib import email_helpers
from lib.job.email import EmailJob


class EmailReportJob(EmailJob):

    #pylint: disable=arguments-differ
    def _process(self):
        # determine the template by the category in the future.
        # For now we have only website templates!

        run = DB().fetch_one(
            '''
                SELECT r.name,
                    (SELECT array_agg(t.name) FROM unnest(r.category_ids) as elements
                    LEFT JOIN categories as t on t.id = elements) as categories,
                    m.description as machine_description, m.id as machine_id,
                    r.uri, r.filename, r.branch, r.usage_scenario_variables, r.created_at
                FROM runs r
                LEFT JOIN machines m ON m.id = r.machine_id
                WHERE r.id = %s
                GROUP BY r.id, m.id
            ''',
            params=(self._run_id, ),
            fetch_mode='dict')

        # For later if we want to show more data
        # phase_stats = DB().fetch_all("""
        #     SELECT metric, detail_name, value, unit
        #     FROM phase_stats
        #     WHERE
        #         run_id=%s
        #         AND (
        #             metric = 'phase_time_syscall_system'
        #             OR
        #             metric = 'cpu_power_rapl_msr_component'
        #             OR
        #             metric = 'network_carbon_formula_global'
        #             OR
        #             (metric = 'network_total_cgroup_container' AND detail_name = 'gmt-playwright-nodejs')
        #         )
        #         AND phase = '004_[RUNTIME]'
        #     """,
        #     params=(self._run_id, ),
        #     fetch_mode='dict')


        # measurement_data = {
        #     'CPU_POWER': 0,
        #     'CPU_ENERGY_10K': 0,
        #     'NETWORK_CARBON_10K': 0,
        #     'NETWORK_TRANSFER': 0,
        # }

        # for phase_stat in phase_stats:
        #     if metric == 'cpu_power_rapl_msr_component': # for every CPU Package
        #         if unit != 'mW':
        #             raise ValueError(f"Unexpected unit: {unit} for {metric} in run {self._run_id}")
        #         measurement_data['CPU_POWER'] += phase_stat['value']/1000
        #         measurement_data['CPU_ENERGY'] += phase_stat['value']/1000
        #     elif metric == 'network_carbon_formula_global': # for every CPU Package
        #         if unit != 'ug':
        #             raise ValueError(f"Unexpected unit: {unit} for {metric} in run {self._run_id}")
        #         measurement_data['NETWORK_CARBON_10K'] += phase_stat['value']/1_000_0 # /1e9 for kg * 1e5 for 10k visitors
        #     elif metric == 'network_total_cgroup_container': # for every CPU Package
        #         if unit != 'Bytes':
        #             raise ValueError(f"Unexpected unit: {unit} for {metric} in run {self._run_id}")
        #         measurement_data['NETWORK_TRANSFER'] += phase_stat['value']/1e6


        if run['categories'] and 'Websites' in run['categories']:
            title = f"webNRG⚡️ run '{run['name']}' successfully processed on Green Metrics Tool Cluster"
            text_template_path = os.path.join(GMT_DIR, 'templates/emails/email_report_website.txt')
            html_template_path = os.path.join(GMT_DIR, 'templates/emails/email_report_website.html')
        else:
            title = f"Run '{run['name']}' successfully processed on Green Metrics Tool Cluster"
            text_template_path = os.path.join(GMT_DIR, 'templates/emails/email_report_general.txt')
            html_template_path = os.path.join(GMT_DIR, 'templates/emails/email_report_general.html')

        with open(text_template_path, 'r', encoding='UTF-8') as f:
            text_template = f.read()
        with open(html_template_path, 'r', encoding='UTF-8') as f:
            html_template = f.read()

        text_template = replace_variables(text_template, self._run_id, run)
        html_template = replace_variables(html_template, self._run_id, run)

        email_helpers.send_email(
            self._email,
            title,
            text_template,
            html_template
        )


def replace_variables(template, run_id, run):
    # run
    template = template.replace('{{__GMT_RUN_ID__}}', str(run_id))
    template = template.replace('{{__GMT_RUN_NAME__}}', run['name'])
    template = template.replace('{{__GMT_RUN_REPO__}}', run['uri'])
    template = template.replace('{{__GMT_RUN_FILENAME__}}', run['filename'])
    template = template.replace('{{__GMT_RUN_BRANCH__}}', run['branch'])
    template = template.replace('{{__GMT_RUN_MACHINE__}}', f"{run['machine_description']} ({run['machine_id']})")
    template = template.replace('{{__GMT_RUN_DATE__}}', datetime.fromisoformat(str(run['created_at'])).astimezone().strftime("%Y-%m-%d %H:%M %z"))

    # optionals
    template = template.replace('{{__GMT_VAR_PAGE__}}', run.get('usage_scenario_variables',{}).get('__GMT_VAR_PAGE__', '-'))

    # general
    template = template.replace('{{__GMT_DASHBOARD_URL__}}', GlobalConfig().config['cluster']['metrics_url'])

    return template
