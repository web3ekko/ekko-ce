/**
 * Notification Service
 * 
 * Enhanced notification system with priority queue,
 * Alert Drop animations, and accessibility features
 */

import { notifications as mantineNotifications } from '@mantine/notifications'
import React from 'react'
import { IconAlertCircle, IconAlertTriangle, IconInfoCircle, IconCheck, IconBell } from '@tabler/icons-react'

export type NotificationSeverity = 'info' | 'warning' | 'error' | 'success' | 'critical'
export type NotificationPriority = 'low' | 'medium' | 'high' | 'critical'

interface NotificationOptions {
  id?: string
  title: string
  message?: string
  severity?: NotificationSeverity
  priority?: NotificationPriority
  alertType?: string
  autoClose?: number | false
  withSound?: boolean
  onClose?: () => void
  action?: {
    label: string
    onClick: () => void
  }
}

interface QueuedNotification extends NotificationOptions {
  id: string
  timestamp: string
  priority: NotificationPriority
}

const severityConfig = {
  info: {
    color: 'blue',
    icon: IconInfoCircle,
    sound: '/sounds/info.mp3',
  },
  warning: {
    color: 'yellow',
    icon: IconAlertTriangle,
    sound: '/sounds/warning.mp3',
  },
  error: {
    color: 'red',
    icon: IconAlertCircle,
    sound: '/sounds/error.mp3',
  },
  success: {
    color: 'green',
    icon: IconCheck,
    sound: '/sounds/success.mp3',
  },
  critical: {
    color: 'red',
    icon: IconBell,
    sound: '/sounds/critical.mp3',
  },
}

class NotificationService {
  private static instance: NotificationService
  private notificationQueue: QueuedNotification[] = []
  private activeNotifications: Set<string> = new Set()
  private maxConcurrent = 3
  private soundEnabled = true
  private reducedMotion = false

  private constructor() {
    // Check user preferences
    this.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    
    // Listen for preference changes
    window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', (e) => {
      this.reducedMotion = e.matches
    })
    
    // Load sound preference from localStorage
    const savedSoundPref = localStorage.getItem('ekko-notification-sound')
    if (savedSoundPref !== null) {
      this.soundEnabled = savedSoundPref === 'true'
    }
  }

  static getInstance(): NotificationService {
    if (!NotificationService.instance) {
      NotificationService.instance = new NotificationService()
    }
    return NotificationService.instance
  }

  /**
   * Show a notification with Alert Drop animation
   */
  show(options: NotificationOptions): string {
    const id = options.id || `notification-${Date.now()}`
    
    const notification: QueuedNotification = {
      ...options,
      id,
      timestamp: new Date().toISOString(),
      priority: options.priority || 'medium',
    }

    // Critical notifications bypass queue
    if (notification.priority === 'critical') {
      this.showNotification(notification)
      return id
    }

    // Add to queue
    this.notificationQueue.push(notification)
    this.notificationQueue.sort((a, b) => {
      const priorityOrder = { low: 0, medium: 1, high: 2, critical: 3 }
      return priorityOrder[b.priority] - priorityOrder[a.priority]
    })

    // Process queue
    this.processQueue()
    
    return id
  }

  /**
   * Show critical alert (bypasses queue)
   */
  showCritical(options: Omit<NotificationOptions, 'priority' | 'severity'>): string {
    return this.show({
      ...options,
      severity: 'critical',
      priority: 'critical',
      autoClose: false, // Critical alerts require manual dismissal
    })
  }

  /**
   * Show success notification
   */
  showSuccess(title: string, message?: string): string {
    return this.show({
      title,
      message,
      severity: 'success',
      autoClose: 5000,
    })
  }

  /**
   * Show error notification
   */
  showError(title: string, message?: string): string {
    return this.show({
      title,
      message,
      severity: 'error',
      autoClose: 8000,
    })
  }

  /**
   * Show warning notification
   */
  showWarning(title: string, message?: string): string {
    return this.show({
      title,
      message,
      severity: 'warning',
      autoClose: 6000,
    })
  }

  /**
   * Show info notification
   */
  showInfo(title: string, message?: string): string {
    return this.show({
      title,
      message,
      severity: 'info',
      autoClose: 5000,
    })
  }

  /**
   * Hide a notification
   */
  hide(id: string): void {
    mantineNotifications.hide(id)
    this.activeNotifications.delete(id)
    this.processQueue()
  }

  /**
   * Hide all notifications
   */
  hideAll(): void {
    mantineNotifications.clean()
    this.activeNotifications.clear()
    this.notificationQueue = []
  }

  /**
   * Toggle sound on/off
   */
  toggleSound(): boolean {
    this.soundEnabled = !this.soundEnabled
    localStorage.setItem('ekko-notification-sound', String(this.soundEnabled))
    return this.soundEnabled
  }

  /**
   * Get sound enabled state
   */
  isSoundEnabled(): boolean {
    return this.soundEnabled && !this.reducedMotion
  }

  /**
   * Get notification history
   */
  getHistory(): QueuedNotification[] {
    return [...this.notificationQueue]
  }

  private showNotification(notification: QueuedNotification): void {
    const { 
      id, 
      title, 
      message, 
      severity = 'info', 
      autoClose = this.getAutoCloseTime(severity),
      withSound = true,
      onClose,
    } = notification

    // Add to active set
    this.activeNotifications.add(id)

    const config = severityConfig[severity]
    const Icon = config.icon

    // Play sound if enabled
    if (withSound && this.isSoundEnabled() && config.sound) {
      const audio = new Audio(config.sound)
      audio.volume = 0.3
      audio.play().catch(() => {
        // Ignore audio play errors
      })
    }

    // Show notification
    mantineNotifications.show({
      id,
      title,
      message,
      autoClose,
      color: config.color,
      icon: React.createElement(Icon, { size: 20 }),
      withCloseButton: true,
      onClose: () => {
        this.activeNotifications.delete(id)
        onClose?.()
        this.processQueue()
      },
      styles: {
        root: {
          '&[data-mantine-notification]': {
            animation: this.reducedMotion ? 'none' : 'alertDrop 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
          },
        },
      },
    })
  }

  private processQueue(): void {
    if (this.activeNotifications.size >= this.maxConcurrent) {
      return
    }

    const availableSlots = this.maxConcurrent - this.activeNotifications.size
    const toShow = this.notificationQueue.splice(0, availableSlots)

    toShow.forEach(notification => {
      this.showNotification(notification)
    })
  }

  private getAutoCloseTime(severity: NotificationSeverity): number | false {
    switch (severity) {
      case 'critical':
        return false // Requires manual dismissal
      case 'error':
        return 8000
      case 'warning':
        return 6000
      case 'success':
        return 5000
      case 'info':
      default:
        return 5000
    }
  }
}

// Export singleton instance
export const notificationService = NotificationService.getInstance()

// React hook for using notifications
export function useNotifications() {
  return {
    show: notificationService.show.bind(notificationService),
    showCritical: notificationService.showCritical.bind(notificationService),
    showSuccess: notificationService.showSuccess.bind(notificationService),
    showError: notificationService.showError.bind(notificationService),
    showWarning: notificationService.showWarning.bind(notificationService),
    showInfo: notificationService.showInfo.bind(notificationService),
    hide: notificationService.hide.bind(notificationService),
    hideAll: notificationService.hideAll.bind(notificationService),
    toggleSound: notificationService.toggleSound.bind(notificationService),
    isSoundEnabled: notificationService.isSoundEnabled.bind(notificationService),
  }
}