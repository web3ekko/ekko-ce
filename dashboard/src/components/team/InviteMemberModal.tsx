import { useState } from 'react'
import { Modal, Stack, TextInput, Select, Group, Button } from '@mantine/core'

interface InviteMemberModalProps {
    opened: boolean
    onClose: () => void
    onSubmit: (data: any) => void
}

export function InviteMemberModal({ opened, onClose, onSubmit }: InviteMemberModalProps) {
    const [formData, setFormData] = useState({
        email: '',
        role: 'member'
    })

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        onSubmit(formData)
        setFormData({ email: '', role: 'member' })
    }

    return (
        <Modal opened={opened} onClose={onClose} title="Invite Team Member" size="md">
            <form onSubmit={handleSubmit}>
                <Stack gap="md">
                    <TextInput
                        label="Email Address"
                        placeholder="colleague@company.com"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        required
                    />

                    <Select
                        label="Role"
                        value={formData.role}
                        onChange={(value) => setFormData({ ...formData, role: value || 'member' })}
                        data={[
                            { value: 'viewer', label: 'Viewer - Read-only access' },
                            { value: 'member', label: 'Member - Standard access' },
                            { value: 'admin', label: 'Admin - Full management access' }
                        ]}
                    />

                    <Group justify="flex-end" mt="md">
                        <Button variant="subtle" onClick={onClose}>
                            Cancel
                        </Button>
                        <Button type="submit" style={{ backgroundColor: '#2563EB' }}>
                            Send Invitation
                        </Button>
                    </Group>
                </Stack>
            </form>
        </Modal>
    )
}
