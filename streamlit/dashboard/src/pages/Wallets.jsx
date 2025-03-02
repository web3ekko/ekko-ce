import React, { useState } from 'react';
import { 
  Title, 
  Text, 
  Grid, 
  Card, 
  Flex,
  TextInput,
  Button,
  Select,
  SelectItem,
} from '@tremor/react';
import useStore from '../store/store';

const WalletCard = ({ wallet }) => {
  return (
    <Card className="hover:shadow-md transition-all">
      <Flex alignItems="start" justifyContent="between">
        <div>
          <Text className="font-medium">{wallet.name}</Text>
          <Text className="text-gray-500 truncate">{wallet.address}</Text>
          <Text className="text-gray-500 mt-2">
            {wallet.balance} {wallet.blockchain}
          </Text>
        </div>
        <div className="text-right">
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            {wallet.blockchain}
          </span>
        </div>
      </Flex>
    </Card>
  );
};

const Wallets = () => {
  const { wallets, addWallet, selectedBlockchain } = useStore();
  const [newWalletAddress, setNewWalletAddress] = useState('');
  const [newWalletName, setNewWalletName] = useState('');
  const [newWalletBlockchain, setNewWalletBlockchain] = useState(selectedBlockchain);

  const blockchains = [
    { value: 'ETH', name: 'Ethereum' },
    { value: 'AVAX', name: 'Avalanche' },
    { value: 'MATIC', name: 'Polygon' },
    { value: 'BTC', name: 'Bitcoin' }
  ];

  const handleAddWallet = () => {
    if (!newWalletAddress) return;

    const newWallet = {
      id: wallets.length + 1,
      name: newWalletName || `Wallet ${wallets.length + 1}`,
      address: newWalletAddress,
      blockchain: newWalletBlockchain,
      balance: 0
    };

    addWallet(newWallet);
    setNewWalletAddress('');
    setNewWalletName('');
  };

  // Filter wallets by selected blockchain if needed
  const filteredWallets = selectedBlockchain === 'All' 
    ? wallets 
    : wallets.filter(wallet => wallet.blockchain === selectedBlockchain);

  return (
    <div>
      <Title>Wallets</Title>
      <Text>Manage your crypto wallets</Text>

      <Grid numItemsMd={3} className="mt-6 gap-6">
        <div className="md:col-span-2">
          <Title>Connected Wallets</Title>
          <div className="mt-4 space-y-4">
            {filteredWallets.length === 0 ? (
              <Card>
                <Text>No wallets found for {selectedBlockchain}</Text>
              </Card>
            ) : (
              filteredWallets.map((wallet) => (
                <WalletCard key={wallet.id} wallet={wallet} />
              ))
            )}
          </div>
        </div>

        <div>
          <Card>
            <Title>Add New Wallet</Title>
            <div className="mt-4 space-y-4">
              <div>
                <Text>Wallet Address</Text>
                <TextInput
                  placeholder="0x..."
                  value={newWalletAddress}
                  onChange={(e) => setNewWalletAddress(e.target.value)}
                />
              </div>
              <div>
                <Text>Wallet Name (optional)</Text>
                <TextInput
                  placeholder="My Wallet"
                  value={newWalletName}
                  onChange={(e) => setNewWalletName(e.target.value)}
                />
              </div>
              <div>
                <Text>Blockchain</Text>
                <Select
                  value={newWalletBlockchain}
                  onValueChange={setNewWalletBlockchain}
                >
                  {blockchains.map((blockchain) => (
                    <SelectItem key={blockchain.value} value={blockchain.value}>
                      {blockchain.name}
                    </SelectItem>
                  ))}
                </Select>
              </div>
              <Button onClick={handleAddWallet} className="mt-4 w-full">
                Connect Wallet
              </Button>
            </div>
          </Card>
        </div>
      </Grid>
    </div>
  );
};

export default Wallets;
