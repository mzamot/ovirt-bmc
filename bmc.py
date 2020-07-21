#!/usr/bin/env python3

import argparse
import os
import sys
import time
import ovirtsdk4 as sdk
import ovirtsdk4.types as types
import configparser
import pyghmi.ipmi.bmc as bmc

class OvirtBmc(bmc.Bmc):
    def __init__(self, authdata, ovirt, address, port, instance):
        super(OvirtBmc, self).__init__(authdata, port=port, address=address)

        self.ovirt = ovirt
        self.connection = sdk.Connection(
                url=self.ovirt['url'], 
                username=self.ovirt['user'],
                password=self.ovirt['pass'],
                insecure=self.ovirt['insecure']
                )

        self.vms_service = self.connection.system_service().vms_service()
        self.server = None
        self.instance = None
        self.isActive = False

        while True:
                self.instance = self.vms_service.list(search='name={}'.format(instance))[0]
                self.server = self.vms_service.vm_service(self.instance.id)
                self.isActive = self.get_state()
                if self.instance is not None:
                    self.log('Managing instance: %s ID: %s' %
                             (self.instance.name, self.instance.id))
                    break

    def get_boot_device(self):
        """Return the currently configured boot device"""
        retval = self.server.get().os.boot.devices[0]
        self.log('Reporting boot device', retval)
        return retval
    
    def set_boot_device(self, bootdevice):
        if bootdevice == 'network':
            self.server.update(vm=types.Vm(os=types.OperatingSystem(boot=types.Boot(devices=[types.BootDevice.NETWORK]))))
        else:
            self.server.update(vm=types.Vm(os=types.OperatingSystem(boot=types.Boot(devices=[types.BootDevice.HD]))))
        self.log('Set boot device to', bootdevice)
       
    def cold_reset(self):
        self.log('Shutting down in response to BMC cold reset request')
        sys.exit(0)

    def get_state(self):
        self.server.get().status
        if self.server.get().status in (types.VmStatus.UP, types.VmStatus.WAIT_FOR_LAUNCH, types.VmStatus.POWERING_UP):
            return True
        else:
            return False

    def get_power_state(self):
        if self.get_state():
            return 'on'
        else:
            return 'off'

    def power_off(self):
        if self.get_state():
            try:
                self.server.stop()
                self.log('Powered off %s' % self.instance.id)
            except exceptions.Conflict as e:
                self.log('Ignoring exception: "%s"' % e)
        else:
            self.log('%s is already off.' % self.instance.id)

    def power_on(self):
        if not self.get_state():
          self.server.start()
          self.log('Powered on %s' % self.instance.id)
        else:
            self.log('%s is already on.' % self.instance.id)

    def power_reset(self):
        print('WARNING: Received request for unimplemented action power_reset')

    def power_shutdown(self):
        if self.target_status == 'off':
            return 0xd5
        self.target_status = 'off'
        self.server.shutdown()
        self.log('Politely shut down %s' % self.instance)

    def log(self, *msg):
        print(' '.join(msg))
        sys.stdout.flush()

def main():
    servers = []
    config = configparser.ConfigParser()
    config.read('bmc.conf')

    ovirt_auth = { 'user': config['DEFAULT']['ovirt_username'], 
                   'pass': config['DEFAULT']['ovirt_password'],
                   'url': config['DEFAULT']['ovirt_fqdn'],
                   'insecure': True }

    address = config['DEFAULT']['listen']
    addr_format = '%s'
    if ':' not in address:
        addr_format = '::ffff:%s'
    
    for server in config.sections():
        name = server
        username = config[server]["username"]
        password = config[server]["password"]
        ipmi_auth = {
            config[server]["username"]: config[server]["password"] }
        port = int(config[server]["port"])
        servers.append(OvirtBmc(ipmi_auth, ovirt_auth, address='::', port=port,
                         instance=name))

    for server in servers:
        server.listen()

if __name__ == '__main__':
    main()
