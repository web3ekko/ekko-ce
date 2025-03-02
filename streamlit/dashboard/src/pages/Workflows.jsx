import React, { useState } from 'react';
import { 
  Title, 
  Text, 
  Card, 
  Button,
  TextInput,
  Select,
  SelectItem,
  Grid,
  Col,
  Flex,
  Badge
} from '@tremor/react';
import useStore from '../store/store';

const WorkflowCard = ({ workflow }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'Active': return 'emerald';
      case 'Pending': return 'amber';
      case 'Paused': return 'gray';
      default: return 'blue';
    }
  };

  return (
    <Card className="hover:shadow-md transition-all">
      <Flex alignItems="start" justifyContent="between">
        <div>
          <Text className="font-medium">{workflow.name}</Text>
          <Text className="text-gray-500 mt-1">{workflow.description}</Text>
          <Text className="text-gray-500 mt-2">
            Last run: {workflow.lastRun || 'Never'}
          </Text>
        </div>
        <div className="text-right">
          <Badge color={getStatusColor(workflow.status)}>
            {workflow.status}
          </Badge>
          <div className="mt-2">
            <span className="text-xs text-gray-500">
              Schedule: {workflow.schedule}
            </span>
          </div>
          <div className="mt-1">
            <span className="text-xs text-gray-500">
              Risk: {workflow.riskLevel}
            </span>
          </div>
        </div>
      </Flex>
    </Card>
  );
};

const Workflows = () => {
  const { workflows, addWorkflow } = useStore();
  const [showCreateWorkflow, setShowCreateWorkflow] = useState(false);
  const [description, setDescription] = useState('');
  const [schedule, setSchedule] = useState('Daily');
  const [riskLevel, setRiskLevel] = useState('Medium');

  const scheduleOptions = ['Manual', 'Daily', 'Weekly', 'Monthly'];
  const riskLevelOptions = ['Low', 'Medium', 'High'];

  const handleCreateWorkflow = () => {
    if (!description) return;

    const newWorkflow = {
      id: workflows.length + 1,
      name: description,
      description: description,
      schedule: schedule,
      riskLevel: riskLevel,
      status: 'Pending',
      lastRun: null
    };

    addWorkflow(newWorkflow);
    setDescription('');
    setShowCreateWorkflow(false);
  };

  return (
    <div>
      <Title>Workflows</Title>
      <Text>Manage your automated workflows</Text>

      {/* Create New Workflow */}
      <Card className="mt-6">
        <Flex justifyContent="between" alignItems="center">
          <Title>Create New Workflow</Title>
          <Button 
            onClick={() => setShowCreateWorkflow(!showCreateWorkflow)}
            size="xs"
          >
            {showCreateWorkflow ? 'Cancel' : 'Create Workflow'}
          </Button>
        </Flex>

        {showCreateWorkflow && (
          <div className="mt-4">
            <Text>Describe your workflow</Text>
            <TextInput
              placeholder="Enter workflow description..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="mt-2"
            />

            <Grid numItemsMd={2} className="mt-4 gap-4">
              <Col>
                <Text>Schedule</Text>
                <Select
                  value={schedule}
                  onValueChange={setSchedule}
                  className="mt-2"
                >
                  {scheduleOptions.map(option => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </Select>
              </Col>
              <Col>
                <Text>Risk Level</Text>
                <Select
                  value={riskLevel}
                  onValueChange={setRiskLevel}
                  className="mt-2"
                >
                  {riskLevelOptions.map(option => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </Select>
              </Col>
            </Grid>

            <Button onClick={handleCreateWorkflow} className="mt-4">
              Create Workflow
            </Button>
          </div>
        )}
      </Card>

      {/* Workflow List */}
      <div className="mt-6">
        <Title>Active Workflows</Title>
        <div className="mt-4 space-y-4">
          {workflows.length === 0 ? (
            <Card>
              <Text>No workflows found</Text>
            </Card>
          ) : (
            workflows.map(workflow => (
              <WorkflowCard key={workflow.id} workflow={workflow} />
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default Workflows;
