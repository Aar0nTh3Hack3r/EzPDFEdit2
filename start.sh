#!/bin/bash

cd "$(realpath `dirname ${BASH_SOURCE[0]}`)";
#pwd
#echo $1;

function start () {
    sudo -u sandbox ./app.py;
}
function stop (){
    sudo -u sandbox /usr/bin/pkill -f 'python3 ./app.py';
}

if [ $1 = "start" ]
then
    start;
else
    if [ $1 = "stop" ]
    then
        stop;
    else
        if [ $1 = "restart" ]
        then
            stop;
            start;
        else
            echo "Invalid argument";
        fi
    fi
fi