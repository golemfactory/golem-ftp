# Script for planning QoS for the integration test
docker exec integration-yagna1-1 tc qdisc add dev eth0 root tbf rate 40.0mbit burst 15k latency 25ms
docker exec integration-yagna2-1 tc qdisc add dev eth0 root tbf rate 40.0mbit burst 15k latency 25ms
docker exec integration-yagna1-1 tc qdisc change dev eth0 root netem loss 0% 25% delay 100ms 50ms distribution normal
docker exec integration-yagna1-2 tc qdisc change dev eth0 root netem loss 0% 25% delay 100ms 50ms distribution normal
sleep 30
