#!/bin/bash
echo "mkdir -p $(dirname /datavolume1/$2)" | docker run -i --rm --net 7574-tp1_testing_net -v DataVolume1:/datavolume1 --name $1 busybox
echo "while true; do echo 'Hit CTRL+C\n' >> /datavolume1/$2; sleep 1; done" | docker run -i --rm --net 7574-tp1_testing_net -v DataVolume1:/datavolume1 --name $1 busybox
