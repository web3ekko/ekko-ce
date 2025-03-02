import React from 'react';
import { 
  Title, 
  Text, 
  Grid, 
  Card, 
  Metric, 
  ColGrid, 
  Flex,
  BadgeDelta
} from '@tremor/react';
import { ArrowUpIcon } from '@heroicons/react/24/solid';
import useStore from '../store/store';
import AlertCard from '../components/AlertCard';

const Dashboard = () => {
  const { alerts } = useStore();
  
  const metrics = [
    {
      title: "Total Balance",
      metric: "$45,231.89",
      metricPrev: "$44,120.00",
      delta: "+2.5%",
      deltaType: "increase",
      help: "Total balance across all wallets"
    },
    {
      title: "Active Workflows",
      metric: "12",
      delta: "3 pending approval",
      help: "Number of active workflows"
    },
    {
      title: "AI Agents",
      metric: "5",
      delta: "2 active now",
      help: "Number of AI agents"
    },
  ];

  return (
    <div>
      <Title>Dashboard</Title>
      <Text>Overview of your crypto assets, workflows, and agents</Text>

      {/* Metrics Cards */}
      <Grid numItemsMd={3} className="mt-6 gap-6">
        {metrics.map((item) => (
          <Card key={item.title}>
            <Flex alignItems="start">
              <div>
                <Text>{item.title}</Text>
                <Metric>{item.metric}</Metric>
              </div>
              <BadgeDelta deltaType={item.deltaType || "moderateIncrease"}>
                {item.delta}
              </BadgeDelta>
            </Flex>
          </Card>
        ))}
      </Grid>

      {/* Recent Activities */}
      <Grid numItemsMd={2} className="mt-6 gap-6">
        <Card>
          <Title>Recent Transactions</Title>
          <Text className="mt-4">
            No recent transactions found
          </Text>
        </Card>

        <Card>
          <Title>Recent Alerts</Title>
          <div className="mt-4 space-y-4">
            {alerts.slice(0, 2).map((alert) => (
              <AlertCard key={alert.id} alert={alert} />
            ))}
          </div>
        </Card>
      </Grid>
    </div>
  );
};

export default Dashboard;
