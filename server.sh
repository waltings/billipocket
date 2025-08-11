#!/bin/bash

# Billipocket Server Management Script
# Kasutamine: ./server.sh [start|stop|restart|status]

PIDFILE="billipocket.pid"
LOGFILE="flask.log"
PORT="5010"

start_server() {
    if [ -f $PIDFILE ]; then
        PID=$(cat $PIDFILE)
        if ps -p $PID > /dev/null 2>&1; then
            echo "Server juba töötab (PID: $PID)"
            echo "Logi jälgimiseks: tail -f $LOGFILE"
            echo "Server aadress: http://127.0.0.1:$PORT"
            return 0
        else
            echo "PID fail eksisteerib, aga server ei tööta. Kustutan PID faili..."
            rm -f $PIDFILE
        fi
    fi
    
    echo "Käivitan Billipocket serverit..."
    
    # Vabanesta portist kui vaja
    lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
    
    # Käivita server taustal
    nohup python3 run.py > $LOGFILE 2>&1 &
    SERVER_PID=$!
    
    # Salvesta PID
    echo $SERVER_PID > $PIDFILE
    
    # Oota hetk et server käivituks
    sleep 3
    
    # Kontrolli kas server käivitus
    if ps -p $SERVER_PID > /dev/null 2>&1; then
        echo "✅ Server käivitatud edukalt!"
        echo "📋 PID: $SERVER_PID"
        echo "🌐 URL: http://127.0.0.1:$PORT"
        echo "📝 Logi: tail -f $LOGFILE"
        echo ""
        echo "Serveri seiskamiseks: ./server.sh stop"
    else
        echo "❌ Server ei käivitunud. Vaata logifaili:"
        tail -20 $LOGFILE
        rm -f $PIDFILE
        exit 1
    fi
}

stop_server() {
    if [ ! -f $PIDFILE ]; then
        echo "Server ei tööta (PID faili ei leitud)"
        # Proovin ikkagi portist vabastada
        lsof -ti :$PORT | xargs kill -9 2>/dev/null && echo "Port $PORT vabastatud" || true
        return 0
    fi
    
    PID=$(cat $PIDFILE)
    
    if ps -p $PID > /dev/null 2>&1; then
        echo "Peatan serveri (PID: $PID)..."
        kill $PID
        
        # Oota kuni server seiskub
        for i in {1..10}; do
            if ! ps -p $PID > /dev/null 2>&1; then
                echo "✅ Server peatatud"
                break
            fi
            sleep 1
            echo "Ootan serveri peatumist..."
        done
        
        # Kui ikka töötab, sunni seiskama
        if ps -p $PID > /dev/null 2>&1; then
            echo "Sunni server seiskuma..."
            kill -9 $PID
            echo "✅ Server sunniviisiliselt peatatud"
        fi
    else
        echo "Server ei töötanud (PID: $PID)"
    fi
    
    # Vabanesta portist kindluse mõttes
    lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
    
    rm -f $PIDFILE
}

status_server() {
    if [ -f $PIDFILE ]; then
        PID=$(cat $PIDFILE)
        if ps -p $PID > /dev/null 2>&1; then
            echo "✅ Server töötab"
            echo "📋 PID: $PID"
            echo "🌐 URL: http://127.0.0.1:$PORT"
            echo "📝 Logi: tail -f $LOGFILE"
            
            # Näita CPU ja mälu kasutust
            ps -p $PID -o pid,ppid,%cpu,%mem,cmd 2>/dev/null || true
        else
            echo "❌ Server ei tööta (vana PID: $PID)"
            rm -f $PIDFILE
        fi
    else
        echo "❌ Server ei tööta"
    fi
    
    # Kontrolli kas port on kasutusel
    PORT_USED=$(lsof -ti :$PORT 2>/dev/null)
    if [ ! -z "$PORT_USED" ]; then
        echo "⚠️  Port $PORT on kasutusel (PID: $PORT_USED)"
    fi
}

restart_server() {
    echo "Taaskäivitan serverit..."
    stop_server
    sleep 2
    start_server
}

case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        status_server
        ;;
    *)
        echo "Billipocket Server Manager"
        echo "========================="
        echo ""
        echo "Kasutamine: $0 {start|stop|restart|status}"
        echo ""
        echo "  start   - Käivita server"
        echo "  stop    - Peata server"  
        echo "  restart - Taaskäivita server"
        echo "  status  - Näita serveri olekut"
        echo ""
        exit 1
        ;;
esac

exit 0