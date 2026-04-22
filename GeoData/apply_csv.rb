#!/usr/bin/env ruby

require 'csv'
require 'json'

csv_table = CSV.read("data.csv", headers: true)
geojson = JSON.load(File.open('municipalities.geojson'))

geojson['features'].select do |municipality|
  row_data = csv_table.find { |r| r['lau_1'].to_i == municipality['properties']['lau_1'].to_i }

  municipality['properties'] = {}

  row_data.each do |header, value|
    municipality['properties'][header] = value
  end
end


File.open('municipalities.geojson', 'w') do |file|
  file.write(geojson.to_json)
end