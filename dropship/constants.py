ExternalConnection = "EXTERNAL"

OutDir = "./out"

RequiredVariablesDHCP = ('dhcp_range_start', 'dhcp_range_end')
RequiredVariablesNetwork = ('network_dns_forwarder', 'network_gateway', 'network_prefix', 'network_netmask', 'network_dns_server')
RequiredVariablesDomain = ('domain_long', 'domain_short', 'admin_password', 'admin_username')