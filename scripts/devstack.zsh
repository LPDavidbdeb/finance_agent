#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.dev/run"
LOG_DIR="$ROOT_DIR/logs/dev"

DJANGO_PID="$RUN_DIR/django.pid"
CELERY_PID="$RUN_DIR/celery.pid"
VITE_PID="$RUN_DIR/vite.pid"
REDIS_PID="$RUN_DIR/redis.pid"
REDIS_MODE="$RUN_DIR/redis.mode"

mkdir -p "$RUN_DIR" "$LOG_DIR"

is_pid_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

read_pid() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    tr -d '[:space:]' < "$pid_file"
  fi
}

start_bg_process() {
  local name="$1"
  local pid_file="$2"
  local log_file="$3"
  local cwd="$4"
  local cmd="$5"

  local current_pid
  current_pid="$(read_pid "$pid_file")"
  if [[ -n "${current_pid:-}" ]] && is_pid_running "$current_pid"; then
    echo "$name is already running (pid $current_pid)"
    return 0
  fi

  rm -f "$pid_file"
  (
    cd "$cwd"
    nohup zsh -lc "$cmd" >> "$log_file" 2>&1 &
    echo $! > "$pid_file"
  )

  sleep 1
  current_pid="$(read_pid "$pid_file")"
  if [[ -n "${current_pid:-}" ]] && is_pid_running "$current_pid"; then
    echo "Started $name (pid $current_pid)"
  else
    echo "Failed to start $name. Check $log_file"
    return 1
  fi
}

stop_bg_process() {
  local name="$1"
  local pid_file="$2"
  local pid
  pid="$(read_pid "$pid_file")"

  if [[ -z "${pid:-}" ]]; then
    echo "$name is not running (no pid file)"
    return 0
  fi

  if is_pid_running "$pid"; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    if is_pid_running "$pid"; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    echo "Stopped $name"
  else
    echo "$name pid file was stale"
  fi

  rm -f "$pid_file"
}

redis_is_ready() {
  command -v redis-cli >/dev/null 2>&1 && [[ "$(redis-cli ping 2>/dev/null || true)" == "PONG" ]]
}

start_redis() {
  if redis_is_ready; then
    echo "Redis is already running"
    return 0
  fi

  rm -f "$REDIS_MODE" "$REDIS_PID"

  if command -v brew >/dev/null 2>&1; then
    if brew services start redis >/dev/null 2>&1; then
      echo "brew" > "$REDIS_MODE"
      sleep 1
      if redis_is_ready; then
        echo "Started Redis via Homebrew service"
        return 0
      fi
    elif brew services start redis@7 >/dev/null 2>&1; then
      echo "brew" > "$REDIS_MODE"
      sleep 1
      if redis_is_ready; then
        echo "Started Redis via Homebrew service (redis@7)"
        return 0
      fi
    fi
  fi

  if command -v redis-server >/dev/null 2>&1; then
    nohup redis-server >> "$LOG_DIR/redis.log" 2>&1 &
    echo $! > "$REDIS_PID"
    echo "local" > "$REDIS_MODE"
    sleep 1
    if redis_is_ready; then
      echo "Started Redis via redis-server"
      return 0
    fi
  fi

  echo "Failed to start Redis. Install/start Redis manually."
  return 1
}

stop_redis() {
  local mode=""
  [[ -f "$REDIS_MODE" ]] && mode="$(cat "$REDIS_MODE")"

  if [[ "$mode" == "brew" ]] && command -v brew >/dev/null 2>&1; then
    brew services stop redis >/dev/null 2>&1 || brew services stop redis@7 >/dev/null 2>&1 || true
    sleep 1
  elif [[ "$mode" == "local" ]]; then
    stop_bg_process "Redis" "$REDIS_PID"
  else
    if redis_is_ready && command -v redis-cli >/dev/null 2>&1; then
      redis-cli shutdown nosave >/dev/null 2>&1 || true
    fi
  fi

  rm -f "$REDIS_MODE" "$REDIS_PID"

  if redis_is_ready; then
    echo "Redis still appears to be running"
  else
    echo "Redis stopped"
  fi
}

status_line() {
  local name="$1"
  local pid_file="$2"
  local pid
  pid="$(read_pid "$pid_file")"
  if [[ -n "${pid:-}" ]] && is_pid_running "$pid"; then
    echo "$name: running (pid $pid)"
  else
    echo "$name: stopped"
  fi
}

start_all() {
  start_redis
  start_bg_process "Django" "$DJANGO_PID" "$LOG_DIR/django.log" "$ROOT_DIR" "$ROOT_DIR/venv/bin/python manage.py runserver"
  start_bg_process "Celery" "$CELERY_PID" "$LOG_DIR/celery.log" "$ROOT_DIR" "$ROOT_DIR/venv/bin/celery -A finance_backend worker -l info"
  start_bg_process "Vite" "$VITE_PID" "$LOG_DIR/vite.log" "$ROOT_DIR/frontend" "npm run dev -- --host 0.0.0.0 --port 5173"

  echo ""
  echo "Services started. Logs are in $LOG_DIR"
}

stop_all() {
  stop_bg_process "Vite" "$VITE_PID"
  stop_bg_process "Celery" "$CELERY_PID"
  stop_bg_process "Django" "$DJANGO_PID"
  stop_redis
}

status_all() {
  if redis_is_ready; then
    echo "Redis: running"
  else
    echo "Redis: stopped"
  fi
  status_line "Django" "$DJANGO_PID"
  status_line "Celery" "$CELERY_PID"
  status_line "Vite" "$VITE_PID"
}

usage() {
  cat <<EOF
Usage: scripts/devstack.zsh <start|stop|restart|status>

Commands:
  start    Start Redis, Django, Celery worker, and Vite
  stop     Stop Vite, Celery, Django, and Redis
  restart  Restart all services
  status   Print current service status
EOF
}

main() {
  local command="${1:-}"
  case "$command" in
    start)
      start_all
      ;;
    stop)
      stop_all
      ;;
    restart)
      stop_all
      start_all
      ;;
    status)
      status_all
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"

