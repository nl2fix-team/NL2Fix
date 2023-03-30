FROM ubuntu:20.04

#############################################################################
# Requirements
#############################################################################

RUN \
    apt-get update -y && \
    apt-get install software-properties-common -y && \
    apt-get update -y && \
    apt-get install -y openjdk-8* \
    git \
    ant\
    python3\
    python3-pip\
    build-essential \
    subversion \
    perl \
    curl \
    unzip \
    cpanminus \
    make \
    && \
    rm -rf /var/lib/apt/lists/*

# Java version
ENV JAVA_HOME /usr


# Timezone
ENV TZ=America/Los_Angeles
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone


#############################################################################
# Setup Defects4J
#############################################################################

# ----------- Step 1. Clone defects4j from github --------------
WORKDIR /
RUN git clone https://github.com/rjust/defects4j.git defects4j

# ----------- Step 2. Initialize Defects4J ---------------------
WORKDIR /defects4j
RUN cpanm --installdeps .
RUN ./init.sh

# ----------- Step 3. Add Defects4J's executables to PATH: ------
ENV PATH="/defects4j/framework/bin:${PATH}"  

#############################################################################
# Setup nl2fix
#############################################################################

# ----------- Step 4. add nl2fix to docker env: ------
ADD ./ ./nl2fix
#clone instead

# ----------- Step 5. install requirements: ------

RUN pip3 install -r ./nl2fix/requirements.txt


ENTRYPOINT ["/bin/bash"]