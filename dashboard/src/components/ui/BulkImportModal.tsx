/**
 * Bulk Import Modal Component
 *
 * Reusable modal for bulk importing items (wallets, alerts, etc.)
 */

import { useState, useCallback } from 'react'
import {
  Modal,
  Stack,
  Text,
  Card,
  Group,
  Button,
  Paper,
  Progress,
  Badge,
  ThemeIcon,
  Textarea,
  Tabs,
  Code,
  Alert,
} from '@mantine/core'
import { Dropzone } from '@mantine/dropzone'
import {
  IconUpload,
  IconFile,
  IconFileTypeCsv,
  IconBraces,
  IconCheck,
  IconAlertCircle,
  IconX,
} from '@tabler/icons-react'

interface BulkImportModalProps {
  opened: boolean
  onClose: () => void
  title: string
  description?: string
  itemType: string
  csvTemplate?: string
  jsonTemplate?: string
  onImport: (data: string, format: 'csv' | 'json') => Promise<{ success: number; failed: number; errors?: string[] }>
}

export function BulkImportModal({
  opened,
  onClose,
  title,
  description,
  itemType,
  csvTemplate,
  jsonTemplate,
  onImport,
}: BulkImportModalProps) {
  const [activeTab, setActiveTab] = useState<string | null>('upload')
  const [importing, setImporting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState<{ success: number; failed: number; errors?: string[] } | null>(null)
  const [pasteData, setPasteData] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const handleDrop = useCallback((files: File[]) => {
    if (files.length > 0) {
      setSelectedFile(files[0])
      setResult(null)
    }
  }, [])

  const handleImport = async () => {
    if (!selectedFile && !pasteData) return

    setImporting(true)
    setProgress(0)
    setResult(null)

    try {
      let data = ''
      let format: 'csv' | 'json' = 'csv'

      if (selectedFile) {
        data = await selectedFile.text()
        format = selectedFile.name.endsWith('.json') ? 'json' : 'csv'
      } else if (pasteData) {
        data = pasteData
        // Try to detect format
        try {
          JSON.parse(pasteData)
          format = 'json'
        } catch {
          format = 'csv'
        }
      }

      // Simulate progress
      const progressInterval = setInterval(() => {
        setProgress(prev => Math.min(prev + 10, 90))
      }, 100)

      const importResult = await onImport(data, format)

      clearInterval(progressInterval)
      setProgress(100)
      setResult(importResult)

      if (importResult.success > 0 && importResult.failed === 0) {
        setTimeout(() => {
          onClose()
          resetState()
        }, 1500)
      }
    } catch (error) {
      setResult({
        success: 0,
        failed: 1,
        errors: [error instanceof Error ? error.message : 'Import failed'],
      })
    } finally {
      setImporting(false)
    }
  }

  const resetState = () => {
    setSelectedFile(null)
    setPasteData('')
    setProgress(0)
    setResult(null)
    setActiveTab('upload')
  }

  const handleClose = () => {
    resetState()
    onClose()
  }

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title={<Text fw={600} size="sm">{title}</Text>}
      size="lg"
    >
      <Stack gap="md">
        {description && (
          <Text size="sm" c="dimmed">{description}</Text>
        )}

        <Tabs value={activeTab} onChange={setActiveTab}>
          <Tabs.List>
            <Tabs.Tab value="upload" leftSection={<IconUpload size={14} />}>
              Upload File
            </Tabs.Tab>
            <Tabs.Tab value="paste" leftSection={<IconBraces size={14} />}>
              Paste Data
            </Tabs.Tab>
            <Tabs.Tab value="template" leftSection={<IconFile size={14} />}>
              Templates
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="upload" pt="md">
            <Dropzone
              onDrop={handleDrop}
              accept={{
                'text/csv': ['.csv'],
                'application/json': ['.json'],
              }}
              maxSize={5 * 1024 * 1024}
              multiple={false}
            >
              <Group justify="center" gap="xl" mih={120} style={{ pointerEvents: 'none' }}>
                <Dropzone.Accept>
                  <IconCheck size={32} color="var(--mantine-color-green-6)" />
                </Dropzone.Accept>
                <Dropzone.Reject>
                  <IconX size={32} color="var(--mantine-color-red-6)" />
                </Dropzone.Reject>
                <Dropzone.Idle>
                  {selectedFile ? (
                    <Stack align="center" gap="xs">
                      <ThemeIcon size="lg" variant="light" color="blue" radius="xl">
                        {selectedFile.name.endsWith('.json') ? (
                          <IconBraces size={20} />
                        ) : (
                          <IconFileTypeCsv size={20} />
                        )}
                      </ThemeIcon>
                      <Text size="sm" fw={500}>{selectedFile.name}</Text>
                      <Text size="xs" c="dimmed">
                        {(selectedFile.size / 1024).toFixed(1)} KB
                      </Text>
                    </Stack>
                  ) : (
                    <Stack align="center" gap="xs">
                      <IconUpload size={32} color="var(--mantine-color-gray-5)" />
                      <div>
                        <Text size="sm" ta="center">
                          Drop CSV or JSON file here
                        </Text>
                        <Text size="xs" c="dimmed" ta="center">
                          Max file size: 5MB
                        </Text>
                      </div>
                    </Stack>
                  )}
                </Dropzone.Idle>
              </Group>
            </Dropzone>
          </Tabs.Panel>

          <Tabs.Panel value="paste" pt="md">
            <Stack gap="sm">
              <Text size="xs" c="dimmed">
                Paste your CSV or JSON data directly:
              </Text>
              <Textarea
                placeholder={`Paste ${itemType} data here (CSV or JSON format)`}
                minRows={6}
                maxRows={12}
                value={pasteData}
                onChange={(e) => setPasteData(e.target.value)}
                styles={{
                  input: { fontFamily: 'monospace', fontSize: 12 },
                }}
              />
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="template" pt="md">
            <Stack gap="md">
              <Text size="xs" c="dimmed">
                Download templates to ensure correct format:
              </Text>

              {csvTemplate && (
                <Paper p="sm" withBorder>
                  <Group justify="space-between">
                    <Group gap="xs">
                      <ThemeIcon size="sm" variant="light" color="green">
                        <IconFileTypeCsv size={14} />
                      </ThemeIcon>
                      <div>
                        <Text size="sm" fw={500}>CSV Template</Text>
                        <Text size="xs" c="dimmed">Comma-separated values</Text>
                      </div>
                    </Group>
                    <Button size="xs" variant="light">
                      Download
                    </Button>
                  </Group>
                  <Code block mt="xs" style={{ fontSize: 10 }}>
                    {csvTemplate}
                  </Code>
                </Paper>
              )}

              {jsonTemplate && (
                <Paper p="sm" withBorder>
                  <Group justify="space-between">
                    <Group gap="xs">
                      <ThemeIcon size="sm" variant="light" color="blue">
                        <IconBraces size={14} />
                      </ThemeIcon>
                      <div>
                        <Text size="sm" fw={500}>JSON Template</Text>
                        <Text size="xs" c="dimmed">JavaScript Object Notation</Text>
                      </div>
                    </Group>
                    <Button size="xs" variant="light">
                      Download
                    </Button>
                  </Group>
                  <Code block mt="xs" style={{ fontSize: 10 }}>
                    {jsonTemplate}
                  </Code>
                </Paper>
              )}
            </Stack>
          </Tabs.Panel>
        </Tabs>

        {/* Progress */}
        {importing && (
          <Stack gap="xs">
            <Group justify="space-between">
              <Text size="xs" c="dimmed">Importing {itemType}...</Text>
              <Text size="xs" fw={500}>{progress}%</Text>
            </Group>
            <Progress value={progress} size="sm" animated />
          </Stack>
        )}

        {/* Result */}
        {result && (
          <Alert
            color={result.failed === 0 ? 'green' : result.success === 0 ? 'red' : 'yellow'}
            icon={result.failed === 0 ? <IconCheck size={16} /> : <IconAlertCircle size={16} />}
          >
            <Group gap="xs">
              {result.success > 0 && (
                <Badge color="green" variant="light" size="sm">
                  {result.success} imported
                </Badge>
              )}
              {result.failed > 0 && (
                <Badge color="red" variant="light" size="sm">
                  {result.failed} failed
                </Badge>
              )}
            </Group>
            {result.errors && result.errors.length > 0 && (
              <Text size="xs" mt="xs" c="dimmed">
                {result.errors[0]}
              </Text>
            )}
          </Alert>
        )}

        {/* Actions */}
        <Group justify="flex-end" gap="xs">
          <Button variant="subtle" size="xs" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            size="xs"
            onClick={handleImport}
            loading={importing}
            disabled={!selectedFile && !pasteData}
            style={{ backgroundColor: '#2563EB' }}
          >
            Import {itemType}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
