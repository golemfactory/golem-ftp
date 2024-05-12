# Script for planning QoS for the integration test
docker exec integration-yagna1-1 tc qdisc change dev eth0 root netem loss 10.3% 25% delay 200ms 50ms distribution normal
sleep 60
docker exec integration-yagna1-1 tc qdisc change dev eth0 root netem loss 1.3% 25% delay 200ms 50ms distribution normal
docker exec integration-yagna1-2 tc qdisc change dev eth0 root netem loss 1.3% 25% delay 200ms 50ms distribution normal
sleep 60
docker exec integration-yagna1-1 tc qdisc change dev eth0 root netem loss 0.3% 25% delay 20ms
docker exec integration-yagna1-2 tc qdisc change dev eth0 root netem loss 0.3% 25% delay 20ms
