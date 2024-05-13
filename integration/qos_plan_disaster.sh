# Script for planning QoS for the integration test
docker exec integration-relay-1 tc qdisc change dev eth0 root netem rate 4.0mbit delay 100ms 20ms distribution normal
sleep 30
docker exec integration-yagna1-1 tc qdisc change dev eth0 root netem loss 1.3% 25% delay 200ms 50ms distribution normal
docker exec integration-yagna1-2 tc qdisc change dev eth0 root netem loss 1.3% 25% delay 200ms 50ms distribution normal
sleep 30
docker exec integration-yagna1-1 tc qdisc change dev eth0 root netem loss 100% 25% delay 200ms 50ms distribution normal
docker exec integration-yagna1-2 tc qdisc change dev eth0 root netem loss 100% 25% delay 200ms 50ms distribution normal
