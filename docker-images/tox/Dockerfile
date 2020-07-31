FROM cern/cc7-base:latest
RUN \
    yum install -y git gcc openldap-devel krb5-devel mariadb-devel python2-pip python3 && \
    yum clean all --enablerepo='*' && \
    for V in 2 3; do \
        python$V -m pip install --upgrade pip; \
        python$V -m pip install tox coverage; \
    done;