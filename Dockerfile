FROM python:3.7


RUN apt update &&\
    apt install -y git &&\
    apt install -y graphviz 

RUN pip install --upgrade pip
RUN pip install graphviz
RUN pip install cdmcfparser==2.3.2
RUN pip install docstring_parser==0.7
RUN pip install astor

RUN useradd -ms /bin/bash code_user

ENV USER code_user
ENV HOME /home/code_user

RUN cd ${HOME} && git clone https://github.com/defoe-code/defoe.git
WORKDIR ${HOME}

COPY ./code_inspector.py ${HOME}/.
RUN mkdir ${HOME}/staticfg
ADD ./staticfg ${HOME}/staticfg/.

RUN python ${HOME}/code_inspector.py ${HOME}/defoe/defoe/query_utils.py

