FROM cern/cc7-base:latest
ENV PATH="/usr/bin"
RUN yum install -y git gcc python-devel rh-python35 pip
RUN curl https://bootstrap.pypa.io/get-pip.py
RUN python ./get-pip.py
RUN pip install --upgrade pip
RUN pip install --upgrade tox configparser coverage
RUN scl enable rh-python35 'python ./get-pip.py'
RUN scl enable rh-python35 'pip install --upgrade tox configparser coverage'

