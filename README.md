# EuroPython 2015 talk

## Designing a scalable and distributed application

This repository features the **source code** and the **ansible automation playbooks** of the application showcased in my talk.

## Collector source code

It is available as the `ep2015_collector` folder.

## Processor source code

It is available as the `ep2015_processor` folder.

## Ansible

Ansible playbooks are also provided in the `ansible` folder.

They will help you understand in details all the steps followed to build and deploy the entire application stack over multiple 
datacenters.

### requirements

1. The provided ansible playbooks are based on **Gentoo Linux** systems.
2. All machines from the same datacenter are expected to share a local LAN for internal communication.
3. Consul leaders are expected to have a dedicated public IP address and should be able to communicate with each other.

If you use AWS to test this architecture:
* AMI (as of July 2015): ami-30327047 (Pygoscelis-Papua_Gentoo_HVM-2015-07-06-23-43-27)
* Instance Type: t2.small
* VPC: yes, mendatory
* Security Group: inbound *all traffic* from the whole VPC subnet + public IP of the remote consul leader
* ELB: yes (for collectors), optional

### configure your domain

Change to your own domain name in the `ansible/group_vars/all` file.


### configure your hosts' inventory

Add your hosts IPs on the `inventory` file under the following groups:
* eu-west_consuls
* eu-west_collectors
* eu-west_processors
* us-west_consuls
* us-west_collectors
* us-west_processors

### deploy a consul server leader

This topology does not automate the deployment of a multi node consul cluster but just a single consul leader.

Edit the files listed below and set the **public IP** of the **remote** consul leader on the **consul_retry_join_wan** variable:
* group_vars/eu-west
* group_vars/us-west

Then run the playbook:
* `ansible-playbook -i inventory consuls.yml`

### deploy collectors

Edit the files listed below and set the **private IP** of the **local** consul leader on the **consul_server_addr** variable:
* group_vars/eu-west_collectors
* group_vars/us-west_collectors

Then run the playbook:
* `ansible-playbook -i inventory collectors.yml`

### deploy processors
Edit the files listed below and set the **private IP** of the **local** consul leader on the **consul_server_addr** variable:
* group_vars/eu-west_processors
* group_vars/us-west_processors

Then run the playbook:
* `ansible-playbook -i inventory processors.yml`

## Resources
* uWSGI : https://uwsgi-docs.readthedocs.org/en/latest/
* nginx + uWSGI : http://uwsgi-docs.readthedocs.org/en/latest/Nginx.html
* consul : https://www.consul.io
* uWSGI consul plugin : https://github.com/unbit/uwsgi-consul
* consulate : https://github.com/gmr/consulate
* beanstalkd : http://kr.github.io/beanstalkd/
