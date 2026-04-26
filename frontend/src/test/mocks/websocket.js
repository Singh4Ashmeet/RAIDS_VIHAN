export class MockWebSocket {
  constructor(url) {
    this.url = url
    this.readyState = 1
    this.onopen = null
    this.onmessage = null
    this.onclose = null
    this.onerror = null
    MockWebSocket.instance = this
    setTimeout(() => this.onopen?.(), 0)
  }
  send(data) { this._lastSent = data }
  close() { this.onclose?.({ code: 1000 }) }
  simulateMessage(data) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }
  simulateDisconnect() {
    this.readyState = 3
    this.onclose?.({ code: 1006 })
  }
}
