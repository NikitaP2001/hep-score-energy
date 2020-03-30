FROM gitlab-registry.cern.ch/linuxsupport/cc7-base

RUN yum -y update
RUN yum install -y epel-release python-pip && yum clean all

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install --no-cache-dir pyyaml pylint pytest coverage
