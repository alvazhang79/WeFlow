import { app } from 'electron'
import { wcdbService } from './wcdbService'

interface UsageStats {
  appVersion: string
  platform: string
  deviceId: string
  timestamp: number
  online: boolean
  pages: string[]
}

class CloudControlService {
  private deviceId: string = ''
  private timer: NodeJS.Timeout | null = null
  private pages: Set<string> = new Set()

  async init() {
    this.deviceId = this.getDeviceId()
    await wcdbService.cloudInit(300)
    await this.reportOnline()

    this.timer = setInterval(() => {
      this.reportOnline()
    }, 300000)
  }

  private getDeviceId(): string {
    const crypto = require('crypto')
    const os = require('os')
    const machineId = os.hostname() + os.platform() + os.arch()
    return crypto.createHash('md5').update(machineId).digest('hex')
  }

  private async reportOnline() {
    const data: UsageStats = {
      appVersion: app.getVersion(),
      platform: process.platform,
      deviceId: this.deviceId,
      timestamp: Date.now(),
      online: true,
      pages: Array.from(this.pages)
    }

    await wcdbService.cloudReport(JSON.stringify(data))
    this.pages.clear()
  }

  recordPage(pageName: string) {
    this.pages.add(pageName)
  }

  stop() {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
    wcdbService.cloudStop()
  }

  async getLogs() {
    return wcdbService.getLogs()
  }
}

export const cloudControlService = new CloudControlService()


