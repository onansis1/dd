package main

import (
	_ "embed"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"sync/atomic"
	"time"
)

//go:embed index.html
var page []byte

const fixedAddr = "127.0.0.1:47831"

var lastPing int64

func openBrowser(url string) {
	if os.Getenv("NOOPEN") != "" {
		return
	}
	switch runtime.GOOS {
	case "windows":
		_ = exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
	case "darwin":
		_ = exec.Command("open", url).Start()
	default:
		_ = exec.Command("xdg-open", url).Start()
	}
}

func main() {
	ln, err := net.Listen("tcp", fixedAddr)
	if err != nil {
		// 이미 실행 중이면 그 창을 다시 연다
		openBrowser("http://" + fixedAddr)
		return
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		w.Write(page)
	})
	mux.HandleFunc("/favicon.ico", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusNoContent) })
	mux.HandleFunc("/ping", func(w http.ResponseWriter, r *http.Request) {
		atomic.StoreInt64(&lastPing, time.Now().Unix())
		w.WriteHeader(http.StatusNoContent)
	})
	start := time.Now().Unix()
	atomic.StoreInt64(&lastPing, start)
	// 브라우저 탭이 닫혀 핑이 끊기면 스스로 종료
	go func() {
		for {
			time.Sleep(2 * time.Second)
			if time.Now().Unix()-atomic.LoadInt64(&lastPing) > 12 {
				os.Exit(0)
			}
		}
	}()
	go func() {
		time.Sleep(200 * time.Millisecond)
		openBrowser("http://" + fixedAddr)
	}()
	fmt.Println("Survivor Draw running at http://" + fixedAddr)
	_ = http.Serve(ln, mux)
}
