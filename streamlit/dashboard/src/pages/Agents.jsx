import React, { useState } from 'react';
import { 
  Title, 
  Text, 
  Card, 
  Button,
  TextInput,
  Select,
  SelectItem,
  NumberInput,
  Flex,
  Badge
} from '@tremor/react';
import useStore from '../store/store';

const AgentCard = ({ agent }) => {
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
          <Text className="font-medium">{agent.name}</Text>
          <Text className="text-gray-500 mt-1">{agent.description}</Text>
          <Text className="text-gray-500 mt-2">
            Type: {agent.type}
          </Text>
          <Text className="text-gray-500">
            Max Budget: ${agent.maxBudget}
          </Text>
        </div>
        <div className="text-right">
          <Badge color={getStatusColor(agent.status)}>
            {agent.status}
          </Badge>
        </div>
      </Flex>
    </Card>
  );
};

const Agents = () => {
  const { agents, addAgent } = useStore();
  const [showCreateAgent, setShowCreateAgent] = useState(false);
  const [description, setDescription] = useState('');
  const [agentType, setAgentType] = useState('Monitor');
  const [maxBudget, setMaxBudget] = useState(100);

  const agentTypes = ['Monitor', 'Trade', 'Analyze'];

  const handleCreateAgent = () => {
    if (!description) return;

    const newAgent = {
      id: agents.length + 1,
      name: description,
      type: agentType,
      description: description,
      status: 'Pending',
      maxBudget: maxBudget
    };

    addAgent(newAgent);
    setDescription('');
    setShowCreateAgent(false);
  };

  return (
    <div>
      <Title>AI Agents</Title>
      <Text>Manage your autonomous AI agents</Text>

      {/* Create New Agent */}
      <Card className="mt-6">
        <Flex justifyContent="between" alignItems="center">
          <Title>Create New Agent</Title>
          <Button 
            onClick={() => setShowCreateAgent(!showCreateAgent)}
            size="xs"
          >
            {showCreateAgent ? 'Cancel' : 'Create Agent'}
          </Button>
        </Flex>

        {showCreateAgent && (
          <div className="mt-4">
            <Text>What should this agent do?</Text>
            <TextInput
              placeholder="Enter agent description..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="mt-2"
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              <div>
                <Text>Agent Type</Text>
                <Select
                  value={agentType}
                  onValueChange={setAgentType}
                  className="mt-2"
                >
                  {agentTypes.map(type => (
                    <SelectItem key={type} value={type}>
                      {type}
                    </SelectItem>
                  ))}
                </Select>
              </div>
              <div>
                <Text>Max Budget (USD)</Text>
                <NumberInput
                  value={maxBudget}
                  onValueChange={setMaxBudget}
                  min={0}
                  step={10}
                  className="mt-2"
                />
              </div>
            </div>

            <Button onClick={handleCreateAgent} className="mt-4">
              Create Agent
            </Button>
          </div>
        )}
      </Card>

      {/* Agent List */}
      <div className="mt-6">
        <Title>Your Agents</Title>
        <div className="mt-4 space-y-4">
          {agents.length === 0 ? (
            <Card>
              <Text>No agents found</Text>
            </Card>
          ) : (
            agents.map(agent => (
              <AgentCard key={agent.id} agent={agent} />
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default Agents;
