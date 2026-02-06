# Fix health-check messaging link
/name: health-check/,/# ETH Raw/ {
  s/interfaces: \[consumer, publisher\]/interfaces: [handler]/
  /source_config:/,/subscriptions:/ {
    s/health-check-nats-config/health-check-handler/
    s/subscriptions: \["system\.health"\]/subscriptions: "system.health"/
  }
}
