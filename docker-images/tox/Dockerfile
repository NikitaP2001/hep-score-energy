FROM cern/cc7-base:latest
ENV PATH="/usr/bin"
RUN yum install -y git gcc python-devel rh-python35
RUN curl -s https://bootstrap.pypa.io/get-pip.py | python
RUN pip install --upgrade tox
RUN scl enable rh-python35 'pip install --upgrade tox pip'
