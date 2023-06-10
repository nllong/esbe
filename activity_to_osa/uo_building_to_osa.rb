
# TODO: add in the path to the file to convert
require 'openstudio-analysis'

analysis_dir = File.expand_path(File.join(Dir.pwd))
project_dir = File.expand_path(File.join(analysis_dir, '/esbe/activity_2/coincident'))
sim_dir = File.join(project_dir, "run/baseline_scenario/1")
puts "Sim dir: #{sim_dir}"
osw_filename = 'in.osw'

# add this data into default_feature_reports.rb
# Typically in .bundle/install/ruby/2.7.0/gems/urbanopt-reporting-0.7.0/lib/measures/default_feature_reports/measure.xml

=begin
<argument>
    <name>feature_location</name>
    <display_name>URBANopt Feature Location'</display_name>
    <description></description>
    <type>String</type>
    <units></units>
    <required>true</required>
    <model_dependent>false</model_dependent>
    <default_value>1</default_value>
    <min_value></min_value>
    <max_value></max_value>
</argument>
=end

if not File.exists?(sim_dir)
    puts "Could not find #{sim_dir}"
    exit(1)
end

osw_file = File.join(sim_dir, osw_filename)
if not File.exists?(osw_file)
    puts "Could not find #{osw_file}"
    exit(1)
end

puts "Converting OSW to OSA"

a = OpenStudio::Analysis.create('Name of an analysis')
output = a.convert_osw(osw_file)


a.weather_file = File.join(project_dir, 'weather', 'Lecco_IT_TMY.ddy')
a.seed_model = File.join(sim_dir, 'in.osm')


analysis_json = File.join(project_dir, 'analysis.json')
analysis_zip = File.join(project_dir, 'analysis.zip')

a.save(analysis_json)
a.save_osa_zip(analysis_zip)
