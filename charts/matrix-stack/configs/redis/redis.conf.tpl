{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "redis.conf.tpl missing context" .context -}}

# Do not require a password
protected-mode no
port 6379

tcp-backlog 511
tcp-keepalive 300

# Never close the connection
timeout 0

# We run the redis in a container so disable both of these
daemonize no
supervised no

loglevel notice
logfile ''

databases 16
always-show-logo no
stop-writes-on-bgsave-error yes

# We never save to the disk
save ''

replica-serve-stale-data yes
replica-read-only yes
repl-diskless-sync no
repl-diskless-sync-delay 5
repl-diskless-load disabled
repl-disable-tcp-nodelay no
replica-priority 100
acllog-max-len 128

lazyfree-lazy-eviction no
lazyfree-lazy-expire no
lazyfree-lazy-server-del no
replica-lazy-flush no

lazyfree-lazy-user-del no

lazyfree-lazy-user-flush no
oom-score-adj no
oom-score-adj-values 0 200 800

disable-thp yes

appendonly no
appendfilename 'appendonly.aof'
appendfsync everysec

no-appendfsync-on-rewrite no

auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
aof-load-truncated yes
aof-use-rdb-preamble yes
lua-time-limit 5000
slowlog-log-slower-than 10000
slowlog-max-len 128
latency-monitor-threshold 0
notify-keyspace-events ""
hash-max-ziplist-entries 512
hash-max-ziplist-value 64
list-max-ziplist-size -2
list-compress-depth 0
set-max-intset-entries 512
zset-max-ziplist-entries 128
zset-max-ziplist-value 64
hll-sparse-max-bytes 3000
stream-node-max-bytes 4096
stream-node-max-entries 100
activerehashing yes
client-output-buffer-limit normal 0 0 0
client-output-buffer-limit replica 256mb 64mb 60
client-output-buffer-limit pubsub 32mb 8mb 60

# Hz is the freuqency at which background tasks are performed, we keep this low to save CPU
hz 1

# The hz value is increased to scale with the number of clients connected.
dynamic-hz yes

aof-rewrite-incremental-fsync yes
rdb-save-incremental-fsync yes
jemalloc-bg-thread yes

maxmemory {{ .maxMemory }}
maxmemory-policy {{ .maxMemoryPolicy }}
{{- end -}}
