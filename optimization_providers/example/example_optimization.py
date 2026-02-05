# This is an example file that shows how optimizers are implemented.
# When the GMT starts up it looks for all python files in the optimization_providers folder an imports the files.
# The system is designed so that you can include a multitude of reporters with even more optimization functions.
# All functions that have the register_reporter decorator are then registered if they are not listed in the ignore
# list in the config. When registering you have supply a few arguments:
# - The name of the optimizer. This has to be unique and is also the name that that is put in the ignore list
# - The criticality of the optimization if there is an optimization that is set through add_optimization. You can overwrite
#   this in the
# - The name of the general reporter. This is more like a category
# - the icon of the general reporter.
# Once you have decorated the function if gets wrapped into a object and you can access the helper functions through
# the self variable. Please not that this also needs to be the first argument of your function.
#
# You can use the self.add_optimization to generate a message that will be displayed in the frontend. This method
# takes a title and description with an optional link that you can use to point to additional information.

#pylint: disable=unused-argument

from optimization_providers.base import Criticality, register_reporter

REPORTER_NAME = 'GMT core'
REPORTER_ICON = 'diagnoses'

@register_reporter('message_optimization', Criticality.INFO, REPORTER_NAME, REPORTER_ICON)
def message_optimization(self, run, measurements, repo_path, network, notes, phase_stats):
    self.add_optimization('Why am I not seeing more data', '''
                          The Green Metrics Tool is a FOSS software that empowers users to make software more sustainable
                          by measuring energy and carbon. We believe that FOSS is the most beneficial way to go here as
                          transparency is key to create trust, adoption and awareness of the carbon emissions of software.
                          Some features like hosting, automated measurements and also optimizations we use as our angle
                          to support the free continuous development of the tool. So if you use this tool professionally
                          and want to take the step from awareness and measurement to optimization maybe consider
                          supporting us. If you want to use this tool for research, are an NGO or a student please reach
                          out to us - We have special free and reduced priced options. If you don't want to see this
                          message and you are running your own cluster just add the message_optimization to the ignore
                          list into your config file.
                          ''', 'https://www.green-coding.io/products/green-metrics-tool/')

# @register_reporter('example_optimization_test', Criticality.HIGH, REPORTER_NAME, REPORTER_ICON, need_files=True)
# def example_optimization_test(self, run, measurements, repo_path, network, notes, phase_stats):
#     self.add_optimization('You should never see this', 'This is a test for the ignore list!!!')
