import { Server, Response } from 'miragejs';

export default function authFakeApi(server: Server, apiPrefix: string) {
  console.log('Setting up auth routes with prefix:', apiPrefix);

  // Handle the /token endpoint that AuthService calls
  server.post(`/token`, (schema, { requestBody }) => {
    console.log('Mock API /token called with requestBody:', requestBody);
    console.log('Available users in DB:', schema.db.signInUserData);

    // Parse form data (application/x-www-form-urlencoded)
    const params = new URLSearchParams(requestBody);
    const email = params.get('username');
    const password = params.get('password');

    console.log('Parsed credentials:', { email, password });

    const user = schema.db.signInUserData.findBy({
      email,
      password,
    });
    console.log('Found user:', user);

    if (user) {
      console.log('Login successful, returning user:', user);
      return user;
    }
    console.log('Login failed - user not found');
    return new Response(401, { some: 'header' }, { message: 'Invalid email or password!' });
  });

  // Keep the old endpoint for backward compatibility
  server.post(`/users/sign-in`, (schema, { requestBody }) => {
    const { email, password } = JSON.parse(requestBody);
    const user = schema.db.signInUserData.findBy({
      email,
      password,
    });
    console.log('user', user);
    if (user) {
      return user;
    }
    return new Response(401, { some: 'header' }, { message: 'Invalid email or password!' });
  });

  server.post(`${apiPrefix}/sign-out`, () => {
    return true;
  });

  // Mock transactions endpoint
  server.get('/transactions', (schema, request) => {
    console.log('Mock API /transactions called with params:', request.queryParams);

    // Mock transaction data for API response
    const mockApiTransactions = [
      {
        hash: '0x1a2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890',
        from: '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416',
        to: '0x8ba1f109551bD432803012645Hac136c22C177e9',
        value: '2.5',
        gas: '21000',
        gasPrice: '20000000000',
        nonce: '42',
        input: '0x',
        blockNumber: 18500000,
        blockHash: '0xabc123...',
        transactionIndex: 0,
        timestamp: new Date(Date.now() - 300000).toISOString(),
        network: 'avalanche',
        subnet: 'mainnet',
        status: 'confirmed',
        tokenSymbol: 'AVAX',
        transactionType: 'send',
        decodedCall: {
          function: 'Transfer',
          params: { to: '0x8ba1f109551bD432803012645Hac136c22C177e9', value: '2.5' }
        }
      },
      {
        hash: '0x2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890ab',
        from: '0x8ba1f109551bD432803012645Hac136c22C177e9',
        to: '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416',
        value: '1000',
        gas: '21000',
        gasPrice: '20000000000',
        nonce: '43',
        input: '0x',
        blockNumber: 18499950,
        blockHash: '0xdef456...',
        transactionIndex: 1,
        timestamp: new Date(Date.now() - 900000).toISOString(),
        network: 'avalanche',
        subnet: 'mainnet',
        status: 'confirmed',
        tokenSymbol: 'USDC.e',
        transactionType: 'receive',
        decodedCall: {
          function: 'Transfer',
          params: { to: '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416', value: '1000' }
        }
      }
    ];

    const limit = parseInt(request.queryParams.limit) || 20;
    const offset = parseInt(request.queryParams.offset) || 0;

    return {
      transactions: mockApiTransactions.slice(offset, offset + limit),
      total: mockApiTransactions.length,
      limit,
      offset,
      hasMore: offset + limit < mockApiTransactions.length
    };
  });

  // Note: Wallet endpoints removed - using real API exclusively
}
