#!/usr/bin/python
#
#############################################################################################
# Scriptname          : satellite6-automation.py
# Scriptauthor        : Frank Reimer
# Creation date       : 2016-06-23
# License             : GPL v. 3
# Source              : https://github.com/hambuergaer/satellite6_automation
# Issues              : https://github.com/hambuergaer/satellite6_automation/issues
# 
#############################################################################################
#
# Description:
#
# This script helps you to automate host provisioning via Satellite 6 with any 
# orchestration tool (e.g. VMWare Orchestrator) of your choice. It also creates 
# hostgroups in Red Hat IPA server according to your Satellite 6 hostgroups as well
# as an appropriate Red Hat IPA automember rule.
#
# Furthermore it creates Satellite 6 host entries with max. 3 NIC`s:
#
#  1. Nic: this is the primary NIC whis is connected to the public network
#  2. Nic: is for inguest NFS storage which is connected to the storage LAN
#  3. Nic: is for Oracle databases which uses a dedicated network for replication purposes
#
# On **IPA** you need a service user which you will use wihtin this script to interact
# with IPA command line. This user needs sufficient rights in IPA to create host groups
# and add automember rules.
#
#############################################################################################

import json
import sys
import csv
import shlex
import commands
import subprocess
import platform
import os.path
import string
from datetime import datetime
from optparse import OptionParser
from uuid import getnode
from itertools import islice

devnull = open(os.devnull, 'w')

current_date = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
hammer_cmd = "/usr/bin/hammer"
cmd_kdestroy = "/usr/bin/kdestroy"
cmd_kinit = "/usr/bin/kinit"
cmd_klist = "/usr/bin/klist"
cmd_getkeytab = "/usr/sbin/ipa-getkeytab"
cmd_ipa = "/usr/bin/ipa"


class log:
	HEADER	= '\033[0;36m'
	ERROR	= '\033[1;31m'
	INFO	= '\033[0;32m'
	WARN	= '\033[1;33m'
	SUMM	= '\033[1;35m'
	END	= '\033[0m'


def verify_organization(organization):
	cmd_get_orgas = hammer_cmd + " --csv organization list"
	try:
		perform_cmd = subprocess.Popen(cmd_get_orgas, shell=True, stdout=subprocess.PIPE)
		organizations = perform_cmd.stdout.read()
		for line in  islice(organizations.strip().split("\n"), 1, None):	# print output without CSV header
			if organization in line:	
				return True
			else:
				return False

	except:
		print log.ERROR + "ERROR" + log.END
		sys.exit(1)

def verify_location(location):
	cmd_get_locations = hammer_cmd + " --csv location list"
	try:
		perform_cmd = subprocess.Popen(cmd_get_locations, shell=True, stdout=subprocess.PIPE)
		locations = perform_cmd.stdout.read()
		for line in  islice(locations.strip().split("\n"), 1, None):	# print output without CSV header
			if location in line:	
				return True
			else:
				return False

	except:
		print log.ERROR + "ERROR" + log.END
		sys.exit(1)
		
def verify_lifecycle(environment):
        cmd_get_lifecycle = hammer_cmd + " --csv lifecycle-environment list --organization " + ORGANIZATION
        print cmd_get_lifecycle
        try:
                perform_cmd = subprocess.Popen(cmd_get_lifecycle, shell=True, stdout=subprocess.PIPE)
                lifecycle = perform_cmd.stdout.read()
                for line in islice(lifecycle.strip().split("\n"), 1, None):     # print output without CSV header
                        if environment in line:
                                return True
                                break

        except:
                print log.ERROR + "ERROR" + log.END
                sys.exit(1)

def verify_parent_hostgroup(parenthg):
	cmd_get_parent_hostgroup = hammer_cmd + " --csv hostgroup info --name " + parenthg
	try:
		perform_cmd = subprocess.Popen(cmd_get_parent_hostgroup, shell=True, stdout=subprocess.PIPE)
		parenthostgroup = perform_cmd.stdout.read()
		for line in  islice(parenthostgroup.strip().split("\n"), 1, None):	# print output without CSV header
			if parenthg in line:	
				return True
			else:
				return False

	except:
		print log.ERROR + "ERROR" + log.END
		sys.exit(1)

def verify_hostname(hostname):
	cmd_get_hostname = hammer_cmd + " --csv host list"
	try:
		perform_cmd = subprocess.Popen(cmd_get_hostname, shell=True, stdout=subprocess.PIPE)
		find_host = perform_cmd.stdout.read()
		for line in  islice(find_host.strip().split("\n"), 1, None):	# print output without CSV header
			if hostname in line:
				return True
				break
	except:
		print log.ERROR + "ERROR" + log.END
		sys.exit(1)

def create_parent_hostgroup(parenthg,initial_hostgroup):
	cmd_create_parent_hostgroup = hammer_cmd + " hostgroup create --name " + parenthg + " --parent " + initial_hostgroup + " --organizations " + ORGANIZATION + " --locations " + LOCATION
	try:
		perform_cmd = subprocess.Popen(cmd_create_parent_hostgroup, shell=True, stdout=subprocess.PIPE)
		parenthostgroup = perform_cmd.stdout.read()

	except:
		print log.ERROR + "ERROR" + log.END
		sys.exit(1)

def verify_child_hostgroup(childhg):
	cmd_get_child_hostgroup = hammer_cmd + " --csv hostgroup info --name " + childhg
	try:
		perform_cmd = subprocess.Popen(cmd_get_child_hostgroup, shell=True, stdout=subprocess.PIPE)
		childhostgroup = perform_cmd.stdout.read()
		for line in  islice(childhostgroup.strip().split("\n"), 1, None):	# print output without CSV header
			if childhg in line:
				return True
			else:
				return False

	except:
		print log.ERROR + "ERROR" + log.END
		sys.exit(1)

def create_child_hostgroup(childhg,parenthg,puppetenv):
	cmd_create_child_hostgroup = hammer_cmd + " hostgroup create --name " + childhg + " --parent " + parenthg + " --lifecycle-environment " + ENVIRONMENT + " --organizations " + ORGANIZATION + " --environment-id " + puppetenv + " --locations " + LOCATION
	
	try:
		perform_cmd = subprocess.Popen(cmd_create_child_hostgroup, shell=True, stdout=subprocess.PIPE)
		childhostgroup = perform_cmd.stdout.read()

	except:
		print log.ERROR + "ERROR" + log.END
		sys.exit(1)

def create_new_host(client_fqdn,organization,location,hostgroup,partitiontable,puppetenv,*nics):
	if ( PRIMARY_NIC_IP and PRIMARY_NIC_MAC and SUBNET_ID_PRIMARY_NIC ) and not SECONDARY_NIC_IP:
		cmd_create_new_host = hammer_cmd + " host create --name " + client_fqdn + " --organization " + organization + " --location " + location + " --hostgroup " + hostgroup + " --ip " + PRIMARY_NIC_IP + " --mac " + PRIMARY_NIC_MAC + " --subnet-id " + SUBNET_ID_PRIMARY_NIC + " --domain " + DOMAIN + " --realm " + REALM + " --environment-id " + puppetenv + " --puppet-ca-proxy " + PUPPET_CA_PROXY + " --puppet-proxy " + PUPPET_PROXY
	#	print "1. NIC: " + cmd_create_new_host
	
	elif ( ( PRIMARY_NIC_IP and PRIMARY_NIC_MAC and SUBNET_ID_PRIMARY_NIC ) and ( SECONDARY_NIC_IP and SECONDARY_NIC_MAC and SUBNET_ID_SECONDARY_NIC )) and not THIRD_NIC_IP:
		cmd_create_new_host = hammer_cmd + " host create --name " + client_fqdn + " --organization " + organization + " --location " + location + " --hostgroup " + hostgroup + " --ip " + PRIMARY_NIC_IP + " --mac " + PRIMARY_NIC_MAC + " --subnet-id " + SUBNET_ID_PRIMARY_NIC + " --domain " + DOMAIN + " --realm " + REALM + " --environment-id " + puppetenv + " --interface 'type=Nic::Interface,managed=true,mac="+SECONDARY_NIC_MAC+",ip="+SECONDARY_NIC_IP+",subnet_id="+SUBNET_ID_SECONDARY_NIC+",identifier=eth1'" + " --puppet-ca-proxy " + PUPPET_CA_PROXY + " --puppet-proxy " + PUPPET_PROXY
	#	print "2. NICs: " + cmd_create_new_host
	
	elif ( ( PRIMARY_NIC_IP and PRIMARY_NIC_MAC and SUBNET_ID_PRIMARY_NIC ) and ( SECONDARY_NIC_IP and SECONDARY_NIC_MAC and SUBNET_ID_SECONDARY_NIC ) and ( THIRD_NIC_IP and THIRD_NIC_MAC and SUBNET_ID_THIRD_NIC ) ):
		cmd_create_new_host = hammer_cmd + " host create --name " + client_fqdn + " --organization " + organization + " --location " + location + " --hostgroup " + hostgroup + " --ip " + PRIMARY_NIC_IP + " --mac " + PRIMARY_NIC_MAC + " --subnet-id " + SUBNET_ID_PRIMARY_NIC + " --domain " + DOMAIN + " --realm " + REALM + " --environment-id " + puppetenv + " --interface 'type=Nic::Interface,managed=true,mac="+SECONDARY_NIC_MAC+",ip="+SECONDARY_NIC_IP+",subnet_id="+SUBNET_ID_SECONDARY_NIC+",identifier=eth1'" + " --interface 'type=Nic::Interface,managed=true,mac="+THIRD_NIC_MAC+",ip="+THIRD_NIC_IP+",subnet_id="+SUBNET_ID_THIRD_NIC+",identifier=eth2'" + " --puppet-ca-proxy " + PUPPET_CA_PROXY + " --puppet-proxy " + PUPPET_PROXY
	#	print "3. NICs: " + cmd_create_new_host 

	try:
               	perform_cmd = subprocess.Popen(cmd_create_new_host, shell=True, stdout=subprocess.PIPE)
               	childhostgroup = perform_cmd.stdout.read()

 	except:
               	print log.ERROR + "ERROR: could not create host " + client_fqdn + log.END
               	sys.exit(1)

def get_host_iso():
	cmd_get_host_iso = hammer_cmd + " bootdisk host --host " + CLIENT_FQDN + " --file " + NFS_HOST_ISO_STORE + HOSTNAME + ".iso"
        try:
                perform_cmd = subprocess.Popen(cmd_get_host_iso, shell=True, stdout=subprocess.PIPE)
                hostiso = perform_cmd.stdout.read()

        except:
                print log.ERROR + "ERROR: could not download host iso from satellite to " + NFS_HOST_ISO_STORE + log.END
                sys.exit(1)

def get_subnet_id(ip):
	GET_SUBNET = str(ip).split(".")
	SUBNET = str(GET_SUBNET[0]+"."+GET_SUBNET[1]+"."+GET_SUBNET[2] + ".0")
        cmd_get_subnet_id = hammer_cmd + " --csv subnet list"
        try:
                perform_cmd = subprocess.Popen(cmd_get_subnet_id, shell=True, stdout=subprocess.PIPE)
                subnet_id = perform_cmd.stdout.read()
                for line in  islice(subnet_id.strip().split("\n"), 1, None):        # print output without CSV header
                        if SUBNET in line:
                                return line.split(",")[0]
				break

        except:
                print log.ERROR + "ERROR: subnet id not found. Please ensure that the needed subnet " + SUBNET + " is configured properly in Satellite." + log.END
                sys.exit(1)

def verify_subnet(ip):
	GET_SUBNET = str(ip).split(".")
	SUBNET = str(GET_SUBNET[0]+"."+GET_SUBNET[1]+"."+GET_SUBNET[2] + ".0")
        cmd_verify_subnet = hammer_cmd + " --csv subnet list"
        try:
                perform_cmd = subprocess.Popen(cmd_verify_subnet, shell=True, stdout=subprocess.PIPE)
                subnet_id = perform_cmd.stdout.read()
                for line in  islice(subnet_id.strip().split("\n"), 1, None):        # print output without CSV header
                        if SUBNET in line:
                                return True
				break

        except:
                print log.ERROR + "ERROR: subnet not found. Please ensure that the needed subnet " + SUBNET + " is configured properly in Satellite." + log.END

def create_subnet(ip,mask,gateway):
	GET_SUBNET = str(ip).split(".")
	SUBNET = str(GET_SUBNET[0]+"."+GET_SUBNET[1]+"."+GET_SUBNET[2] + ".0")
        cmd_create_subnet = hammer_cmd + " subnet create --boot-mode Static --domains " + DOMAIN + " --locations " + LOCATION + " --name " + SUBNET + " --network " + SUBNET + " --mask " + mask + " --gateway " + gateway +" --organizations " + ORGANIZATION + " --dns-primary " + DNS_PRIMARY + " --ipam None"
        try:
                perform_cmd = subprocess.Popen(cmd_create_subnet, shell=True, stdout=subprocess.PIPE)
                subnet_id = perform_cmd.stdout.read()

        except:
                print log.ERROR + "ERROR: subnet id not found. Please ensure that the needed subnet " + SUBNET + " is configured properly in Satellite." + log.END
                sys.exit(1)

def get_environment_id(default_ccv):
	translation_table = string.maketrans('-','_')
	CONVERT_CCV = DEFAULT_CONTENT_VIEW.translate(translation_table)
	CONVERT_ORGANIZATION = ORGANIZATION.translate(translation_table)
	PUPPET_ENV = str("KT_" + CONVERT_ORGANIZATION + "_" + ENVIRONMENT + "_" + CONVERT_CCV)

        cmd_get_environment_id = hammer_cmd + " --csv environment list"
        try:
                perform_cmd = subprocess.Popen(cmd_get_environment_id, shell=True, stdout=subprocess.PIPE)
                puppet_env_id = perform_cmd.stdout.read()
                for line in  islice(puppet_env_id.strip().split("\n"), 1, None):        # print output without CSV header
                        if PUPPET_ENV in line:
                                return line.split(",")[0]
				break

        except:
                print log.ERROR + "ERROR: Puppet environment id not found. Please ensure that the Puppet environment " + PUPPET_ENV + " is configured properly in Satellite." + log.END
                sys.exit(1)

def update_child_hostgroup(childhg):
	cmd_update_childhg = hammer_cmd + " hostgroup set-parameter --name kt_activation_keys --value " + DEFAULT_ACTIVATION_KEY + " --hostgroup " + childhg

	try:
		perform_cmd = subprocess.Popen(cmd_update_childhg, shell=True, stdout=subprocess.PIPE)
		update_childhostgroup = perform_cmd.stdout.read()

	except:
		print log.ERROR + "ERROR: could not update child hostgroup " + childhg + log.END
		sys.exit(1)

def kerberos_destroy_ticket():
    try:
        subprocess.check_call(cmd_kdestroy, shell=True, stdout=subprocess.PIPE)
    except:
        return False
    return True

def get_kerberos_login_status():
    try:
        subprocess.check_call(cmd_klist, shell=True, stdout=subprocess.PIPE)
    except:
        return False
    return True

def verify_ipa_users_home(user):
    if os.path.exists("/home/"+ user):
        return True
    else:
        return False

def get_keytab(user,kdc,keytab):
    cmd_build_get_keytab = cmd_getkeytab + " -s " + kdc + " -p " + user + " -k " + keytab
    print cmd_build_get_keytab
    try:
        subprocess.call(cmd_build_get_keytab, shell=True, stdout=subprocess.PIPE)
    except:
        print log.ERROR + "ERROR: error getting users keytab. Please check your IPA settings." + log.END
        sys.exit(1)

def get_ticket(user):
    cmd_build_get_ticket = cmd_kinit + " " + user
    try:
        subprocess.call(cmd_build_get_ticket, shell=True, stdout=subprocess.PIPE)
    except:
        print log.ERROR + "ERROR: error getting Kerberos ticket. Please check your IPA settings." + log.END
        sys.exit(1)

def ipa_connect_with_keytab(principal,keytab):
    cmd_connect_with_keytab = cmd_kinit + " -k -t " + keytab + " " + principal
    try:
        subprocess.call(cmd_connect_with_keytab, shell=True, stdout=subprocess.PIPE)
    except:
        print log.ERROR + "ERROR: connection to IPA via keytab did not work." + log.END
        sys.exit(1)

def get_ipa_hostgroup(hostgroup):
    cmd_build_cmd_get_ipahostgroup = cmd_ipa + " hostgroup-find " + hostgroup
    process = subprocess.Popen(shlex.split(cmd_build_cmd_get_ipahostgroup), stdout=subprocess.PIPE)
    process.communicate()
    exit_code = process.wait()
    return exit_code

def create_ipa_hostgroup(hostgroup):
    cmd_build_create_ipahostgroup = cmd_ipa + " hostgroup-add " + hostgroup
    process = subprocess.Popen(shlex.split(cmd_build_create_ipahostgroup), stdout=subprocess.PIPE)
    process.communicate()
    exit_code = process.wait()
    return exit_code

def create_ipa_automember_rule(hostgroup):
    cmd_create_ipa_automember_rule = cmd_ipa + " automember-add --type=hostgroup " + hostgroup
    try:
	perform_cmd = subprocess.Popen(cmd_create_ipa_automember_rule, shell=True, stdout=subprocess.PIPE)
	ipa_automember_rule = perform_cmd.stdout.read()

    except:
	print log.ERROR + "ERROR: could not create IPA automember rule " + hostgroup + log.END
	sys.exit(1)

def create_ipa_automember_rule_condition(hostgroup):
    cmd_create_ipa_automember_rule_condition = cmd_ipa + " automember-add-condition --key=userclass --type=hostgroup --inclusive-regex=" + hostgroup + " " + hostgroup
    try:
	perform_cmd = subprocess.Popen(cmd_create_ipa_automember_rule_condition, shell=True, stdout=subprocess.PIPE)
	ipa_automember_rule = perform_cmd.stdout.read()

    except:
	print log.ERROR + "ERROR: could not create IPA automember rule condition for " + hostgroup + log.END
	sys.exit(1)

def show_ipa_hostgroup(hostgroup):
    IPA_HOSTGROUP = ''
    IPA_HOSTGROUP_MEMBERS = ''
    cmd_build_cmd_show_ipahostgroup = cmd_ipa + " hostgroup-show " + hostgroup
    process = subprocess.Popen(shlex.split(cmd_build_cmd_show_ipahostgroup), stdout=subprocess.PIPE)
    for line in commands.getstatusoutput(cmd_build_cmd_show_ipahostgroup)[1].strip().replace('\n', '').replace('  ',';').split(';'):
        if "Host-group" in line:
                #print line.split(':')[1].strip()
                #IPA_HOSTGROUP.append(line.split(':')[1].strip())
                IPA_HOSTGROUP = line.split(':')[1].strip()
                #return IPA_HOSTGROUP
        if "Member hosts" in line:
                IPA_HOSTGROUP_MEMBERS = line.split(':')[1].strip()
                #return IPA_HOSTGROUP_MEMBERS
    return(IPA_HOSTGROUP,IPA_HOSTGROUP_MEMBERS)

################################## OPTIONS PARSER AND VARIABLES ##################################

parser = OptionParser()
parser.add_option("--satellite-server", dest="sat6_fqdn", help="FQDN of Satellite - omit https://", metavar="SAT6_FQDN")
parser.add_option("--client-fqdn", dest="client_fqdn", help="FQDN of the client you want to deploy", metavar="CLIENT_FQDN")
parser.add_option("--location", dest="location", help="Label of the Location in Satellite that the host is to be associated with", metavar="LOCATION")
parser.add_option("--application-id", dest="application_id", help="Application ID as basis for the hostgroup the client should be assigned to", metavar="APPLICATION_ID")
parser.add_option("--environment", dest="environment", help="Environment should be one of dev/test/preprod/prod", metavar="ENVIRONMENT")
parser.add_option("--partitioning", dest="partitioning", help="Customized partitioning table", metavar="PARTITIONING")
parser.add_option("--primary-nic-ip", dest="primary_nic_ip", help="IP address of the primary/public network interface", metavar="PRIMARY_NIC_IP")
parser.add_option("--primary-nic-mask", dest="primary_nic_mask", help="Subnet mask of primary/public network interface", metavar="PRIMARY_NIC_MASK")
parser.add_option("--primary-nic-gateway", dest="primary_nic_gateway", help="Gateway of primary/public network interface", metavar="PRIMARY_NIC_GATEWAY")
parser.add_option("--primary-nic-mac", dest="primary_nic_mac", help="MAC address of the primary/public network interface", metavar="PRIMARY_NIC_MAC")
parser.add_option("--secondary-nic-ip", dest="secondary_nic_ip", help="IP address of the inguest storage network interface", metavar="SECONDARY_NIC_IP")
parser.add_option("--secondary-nic-mask", dest="secondary_nic_mask", help="Subnet mask of the inguest storage network interface", metavar="SECONDARY_NIC_MASK")
parser.add_option("--secondary-nic-gateway", dest="secondary_nic_gateway", help="Gateway of the inguest storage network interface", metavar="SECONDARY_NIC_GATEWAY")
parser.add_option("--secondary-nic-mac", dest="secondary_nic_mac", help="MAC address of the inguest storage network interface", metavar="SECONDARY_NIC_MAC")
parser.add_option("--third-nic-ip", dest="third_nic_ip", help="IP address of the database replication network interface", metavar="THIRD_NIC_IP")
parser.add_option("--third-nic-mask", dest="third_nic_mask", help="Subnet mask of the database replication network interface", metavar="THIRD_NIC_MASK")
parser.add_option("--third-nic-gateway", dest="third_nic_gateway", help="Gateway of the database replication network interface", metavar="THIRD_NIC_GATEWAY")
parser.add_option("--third-nic-mac", dest="third_nic_mac", help="MAC address of the database replication network interface", metavar="THIRD_NIC_MAC")
parser.add_option("--create-host", dest="create_host", action="store_true", help="Create new host")
parser.add_option("--update-host", dest="update_host", action="store_true", help="Update existing host")
parser.add_option("--intranet", dest="intranet", action="store_true", help="Host should be placed in INTRANET")
parser.add_option("--dmz", dest="dmz", action="store_true", help="Host should be placed in DMZ")
parser.add_option("--application", dest="application", action="store_true", help="True if you want to install an application on the host")
parser.add_option("--infrastructure", dest="infrastructure", action="store_true", help="True if you want to install an infrastructure service on the host")
parser.add_option("-v", "--verbose", dest="verbose", action="store_true", help="Verbose output")
(options, args) = parser.parse_args()

if not (( options.client_fqdn and options.create_host ) or ( options.client_fqdn and options.update_host )):
    print log.ERROR + "You must specify at least client fqdn, the primary NIC information, if you want to create a new host (--create-host) and if you want to deploy your host in intranet or in dmz zone. See usage:\n" + log.END
    parser.print_help()
    print "\nExample usage: ./satellite6-automation.py --client-fqdn client01.example.com --create-host --primary-nic-ip 192.168.100.10 --primary-nic-mask 255.255.255.0 --primary-nic-gateway 192.168.100.1 --primary-nic-mac 00:00:00:00:00:00 --intranet"
    sys.exit(1)
else:
    SAT6_FQDN = options.sat6_fqdn
    CLIENT_FQDN = options.client_fqdn
    HOSTNAME = CLIENT_FQDN.split(".")[0]
    DOMAIN = CLIENT_FQDN.split(".")[1]+"."+CLIENT_FQDN.split(".")[2]
    ORGANIZATION  = ""																		# Change this variable according to your needs
    LOCATION  = options.location
    APPLICATION_ID = str(options.application_id)
    ENVIRONMENT = str(options.environment)
    PARTITIONING = options.partitioning
    PARENT_HOSTGROUP = "hg-"+APPLICATION_ID
    HOSTGROUP = str("hg-"+APPLICATION_ID+"-"+ENVIRONMENT)
    REALM = ""																					# Change this variable according to your IPA realm or make it an option to pass by
    ARCHITECTURE = "x86_64"																# Change this variable according to your needs
    OS = ""																						# Change this variable according to your default operating system or make it an option to pass by
    DEFAULT_CONTENT_VIEW = ""																# Change this variable according to your default content view you want to assign to your hosts or make it an option to pass by
    DEFAULT_ACTIVATION_KEY = ""															# Change this variable according to your default activation key or make it an option to pass by
    PUPPET_ENV_ID = get_environment_id(DEFAULT_CONTENT_VIEW)
    PRINCIPAL = ""																			# Change this variable to your IPA automation service user	
    KDC = ""																					# Change this variable to one of your IPA servers
    KEYTAB = "/home/"+PRINCIPAL+"/"+PRINCIPAL+".keytab"
    NFS_HOST_ISO_STORE = ""																# Change this variable to the NFS mount where you want to store your host iso images (1 MB per ISO)
    DNS_PRIMARY = ""																			# Change this variable to your primary DNS server or make it an option to pass by

if options.primary_nic_ip:
    PRIMARY_NIC_IP = str(options.primary_nic_ip)
    PRIMARY_NIC_MASK = str(options.primary_nic_mask)	
    PRIMARY_NIC_GATEWAY = str(options.primary_nic_gateway) 
    if not verify_subnet(PRIMARY_NIC_IP):
	create_subnet(PRIMARY_NIC_IP,PRIMARY_NIC_MASK,PRIMARY_NIC_GATEWAY)
    SUBNET_ID_PRIMARY_NIC = get_subnet_id(PRIMARY_NIC_IP)
else:
    PRIMARY_NIC_IP = None
    SUBNET_ID_PRIMARY_NIC = None
    PRIMARY_NIC_MASK = None
if options.primary_nic_mac:
    PRIMARY_NIC_MAC = str(options.primary_nic_mac)
else:
    PRIMARY_NIC_MAC = None

if options.secondary_nic_ip:
    SECONDARY_NIC_IP = str(options.secondary_nic_ip)
    SECONDARY_NIC_MASK = str(options.secondary_nic_mask)	
    SECONDARY_NIC_GATEWAY = str(options.secondary_nic_gateway) 
    if not verify_subnet(SECONDARY_NIC_IP):
	create_subnet(SECONDARY_NIC_IP,SECONDARY_NIC_MASK,SECONDARY_NIC_GATEWAY)
    SUBNET_ID_SECONDARY_NIC = get_subnet_id(SECONDARY_NIC_IP)
else:
    SECONDARY_NIC_IP = None     
    SUBNET_ID_SECONDARY_NIC = None
if options.secondary_nic_mac:
    SECONDARY_NIC_MAC = str(options.secondary_nic_mac)
else:
    SECONDARY_NIC_MAC = None

if options.third_nic_ip:
    THIRD_NIC_IP = str(options.third_nic_ip)
    THIRD_NIC_MASK = str(options.third_nic_mask)	
    THIRD_NIC_GATEWAY = str(options.third_nic_gateway) 
    if not verify_subnet(THIRD_NIC_IP):
	create_subnet(THIRD_NIC_IP,THIRD_NIC_MASK,THIRD_NIC_GATEWAY)
    SUBNET_ID_THIRD_NIC = get_subnet_id(THIRD_NIC_IP)
else:
    THIRD_NIC_IP = None
    SUBNET_ID_THIRD_NIC = None
if options.third_nic_mac:
    THIRD_NIC_MAC = str(options.third_nic_mac)
else:
    THIRD_NIC_MAC = None

if options.verbose:
    VERBOSE=True
else:
    VERBOSE=False

if options.create_host:
    CREATE_HOST=True
else:
    CREATE_HOST=False

if options.update_host:
    UPDATE_HOST=True
else:
    UPDATE_HOST=False

if options.intranet:
    INTRANET=True
    PUPPET_PROXY = ""												# Change this variable to your Satellite or Capsule server
    PUPPET_CA_PROXY = ""											# Change this variable to your Satellite or Capsule server
else:
    INTRANET=False

if options.dmz:
    DMZ=True
    PUPPET_PROXY = ""												# Change this variable to your Satellite or Capsule server
    PUPPET_CA_PROXY = ""											# Change this variable to your Satellite or Capsule server
else:
    DMZ=False

if options.application:
    APPLICATION=True
else:
    APPLICATION=False

if options.infrastructure:
    INFRASTRUCTURE=True
else:
    INFRASTRUCTURE=False

if APPLICATION:
	INITIAL_PARENT_HOSTGROUP = ""									# Change this variable to your desired application parent host group
if INFRASTRUCTURE:
	INITIAL_PARENT_HOSTGROUP = ""									# Change this variable to your desired infrastructure parent host group

if VERBOSE:
    print log.SUMM + "### Verbose output ###" + log.END
    print "CLIENT FQDN - %s" % CLIENT_FQDN
    print "ORGANIZATION - %s" % ORGANIZATION
    print "LOCATION - %s" % LOCATION
    print "APPLICATION_ID - %s" % APPLICATION_ID
    print "ENVIRONMENT - %s" % ENVIRONMENT
    print "ENVIRONMENT TABLE - %s" % PARTITIONING
    print "HOSTGROUP - %s" % HOSTGROUP
    print "CREATE_HOST - %s" % CREATE_HOST
    print "UPDATE_HOST - %s" % UPDATE_HOST


################################## MAIN ##################################

##### Verifiying some needed parameters
## Verify organization
if not verify_organization(ORGANIZATION):
	print log.ERROR + "ERROR: Please verify that your organization is configured properly on Satellite." + log.END
	sys.exit(1)

## Verify location
if not verify_location(LOCATION):
	print log.ERROR + "ERROR: Please verify that your location is configured properly on Satellite." + log.END
	sys.exit(1)
	
## Verify lifecycle environment
if not verify_lifecycle(ENVIRONMENT):
        print log.ERROR + "ERROR: Please verify that the lifecycle environment " + ENVIRONMENT + " is configured properly on Satellite." + log.END
        sys.exit(1)

## Verify if Satellite hostgroups are present
if not verify_parent_hostgroup(PARENT_HOSTGROUP):
	print log.ERROR + "ERROR: parent hostgroup " + PARENT_HOSTGROUP  + " not found. Create it now..." + log.END
	create_parent_hostgroup(PARENT_HOSTGROUP,INITIAL_PARENT_HOSTGROUP)
else:
	print log.INFO + "INFO: parent hostgroup " + PARENT_HOSTGROUP + " found. Proceed..." + log.END
if not verify_child_hostgroup(HOSTGROUP):
	print log.ERROR + "ERROR: child hostgroup " + HOSTGROUP  + " not found. Create it now..." + log.END
	create_child_hostgroup(HOSTGROUP,PARENT_HOSTGROUP,PUPPET_ENV_ID)
	update_child_hostgroup(HOSTGROUP)
else:
	print log.INFO + "INFO: child hostgroup " + HOSTGROUP + " found. Proceed..." + log.END

## Verify if IPA hostgroups are present
# Destroy any existing Kerberos ticket first
kerberos_destroy_ticket()

if not os.path.exists(KEYTAB):
	print log.ERROR + "ERROR: did not find Kerberos keytab " + KEYTAB + ". Please make sure that this file exists before you re-run this scipt."
	sys.exit(1)

# Then get valid Kerberos ticket again
if not get_kerberos_login_status():
        print log.ERROR + "ERROR: No valid Kerberos ticket found." + log.END
        print log.INFO + "INFO: try to connect to KDC via keytab file " + log.SUMM + KEYTAB + "." + log.END
        ipa_connect_with_keytab(PRINCIPAL,KEYTAB)
        if get_kerberos_login_status():
                print log.INFO + "INFO: connection to IPA successfully established." + log.END
else:
        print log.INFO + "INFO: Valid Kerberos ticket found." + log.END

# Now lets create needed IPA hostgroup and automember rule
if not get_ipa_hostgroup(HOSTGROUP) == 0:
	print log.WARN + "WARNING: did not find hostgroup " + HOSTGROUP + " on IPA. Will create it now." + log.END
	create_ipa_hostgroup(HOSTGROUP)
	create_ipa_automember_rule(HOSTGROUP)
	create_ipa_automember_rule_condition(HOSTGROUP)
else:
	print log.INFO + "INFO: hostgroup " + HOSTGROUP + " found in IPA." + log.END

##### Now lets create a new host
#verify_hostname(CLIENT_FQDN)

if not verify_hostname(CLIENT_FQDN):
	if (options.client_fqdn and options.create_host):
		create_new_host(HOSTNAME,ORGANIZATION,LOCATION,HOSTGROUP,PARTITIONING,PUPPET_ENV_ID)
		get_host_iso()
	else:
		print log.ERROR + "ERROR: Please see usage of this script: ./satellite6-automation.py --help. It seems that you did not pass the minimum of parameters to this script." + log.END
		sys.exit(1)
else:
	print log.INFO + "INFO: host " + CLIENT_FQDN + " is already present on Satellite. Maybe you want to update the host? If yes, please run this script again with option --update-host instead of --create-host."

