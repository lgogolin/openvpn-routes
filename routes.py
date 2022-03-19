#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys
import logging
import urllib.request
import ipaddress 
import json
import time

# Base path
base_path = "/Library/Application Support/ViscosityScripts/"
# Cache file
backup_file = base_path + "backup"
# Log file
log_file = base_path + "routes.log"
# logging parameters
logging.basicConfig(level=logging.INFO, filename=log_file, filemode='w', format='%(name)s - %(levelname)s - %(message)s')
# Empty CIDR list
cidrs = []

# routes source definition
source_list = [
    { "type": "file",
      "url": "https://assets.zoom.us/docs/ipranges/Zoom.txt"
    },
    {
      "type": "json",
      "path": "git",
      "url": "https://api.github.com/meta"
    },
    {
      "type": "custom",
      "cidrs": ["192.168.0.0/24","192.168.1.0/24"]
    }
]

# Get CIDR list from JSON
def get_json(url, path):
  request = urllib.request.urlopen(url)
  data = request.read()
  json_data = json.loads(data)
  
  return json_data[path]
  
# Convert file lines into CIDR list
def get_file(url):
  request = urllib.request.urlopen(url)
  data = [line.decode('utf8').rstrip() for line in request]
  
  return data

# Add route on a system
def route_add(cidr, gateway):
  cmd = "/sbin/route -n add -net " + cidr + " " + gateway
  route = os.popen(cmd).read()
  logging.debug("Adding route: %s", route.strip())

# Delete route from system
def route_del(cidr, gateway):
  cmd = "/sbin/route delete -net " + cidr + " " + gateway
  route = os.popen(cmd).read()
  logging.debug("Deleting route: %s", route.strip())

# Check CIDR version: IPv4 or IPv6
def cidr_version(cidr):
  ip_net = ipaddress.ip_network(cidr)
  if ip_net.version == 4:
    return True
  else:
    return False

# Compare downloaded CIDRs with cache
def compare(cache_cidrs, new_cidrs):
  cache_cidrs.sort()
  new_cidrs.sort()
  if cache_cidrs != new_cidrs:
    logging.info("We have newer CIDRs list")
    return True
  else:
    return False

# Read CIDRs from backup and return list
def read_backup(backup_file):
  logging.debug("Reading CIDRs from backup: %s", backup_file)
  with open(backup_file) as f:
    lines = f.read().splitlines()
  return lines

# Dump CIDR list to backup file
def populate_backup(cidrs, backup_file):
  logging.debug("Overwriting backup file")
  f=open(backup_file,'w')
  for item in cidrs:
    f.write(item+'\n')

  f.close()

# Main function
if __name__ == "__main__":
  # Get default GW
  logging.debug("Default gateway address: %s", os.environ['route_net_gateway'])
  net_gateway = os.environ['route_net_gateway']

  # do not use backup by default
  use_backup = False
  # Createy backup file if not exist
  if not os.path.exists(backup_file):
    file = open(backup_file, 'w+')
    file.close()

  # route-up - Adding temporary routes
  if sys.argv[1] == "up":
    for item in source_list:
      route_type = item['type']
      # Download JSON type endpoint
      if route_type == "json":
        logging.info("Populating CIDRs from %s", item['url'])
        try:
          json_cidrs = get_json(item['url'], item['path'])
        except Exception as e:
          logging.error("Exception: %s", e)
          use_backup = True
          break
        logging.debug("CIDRs: %s", json_cidrs)
        cidrs += json_cidrs
      # Download file 
      elif route_type == "file":
        logging.info("Populating CIDRs from %s", item['url'])
        try:
          file_cidrs = get_file(item['url'])
        except Exception as e:
          logging.error("Exception: %s", e)
          use_backup = True
          break
        logging.debug("CIDRs: %s", file_cidrs)
        cidrs += file_cidrs
      # Cusomt CIDRs
      elif route_type == "custom":
        logging.info("Populating custom CIDRs")
        logging.debug("CIDRs: %s", item['cidrs'])
        cidrs += item['cidrs']

    logging.debug("CIDR list: %s", cidrs)

    # Adding routes from backup
    if use_backup:
      logging.info("Adding routes from backup")
      for cidr in read_backup(backup_file):
        if cidr_version(cidr):
          route_add(cidr, net_gateway)

    # Adding routes from sources
    else:
      # If CIDRs differ from backup
      if compare(read_backup(backup_file), cidrs):
        populate_backup(cidrs, backup_file)
      
      logging.info("Adding extra routes")
      for cidr in cidrs:
        if cidr_version(cidr):
          route_add(cidr, net_gateway)


  # route-pre-down - Deleting temporary route before stopping VPN
  elif sys.argv[1] == "down": 
    # Read cache from file
    backup = read_backup(backup_file)
    logging.info("Removing extra routes")
    for cidr in backup:
      if cidr_version(cidr):
        route_del(cidr, net_gateway)
      


