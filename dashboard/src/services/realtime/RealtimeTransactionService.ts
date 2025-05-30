import { connect, NatsConnection, Subscription, JSONCodec, StringCodec } from 'nats.ws'; // Import from nats.ws
import store from '@/store'; // Access to store for dispatch and getState
import {
  connectionInitiated,
  connectionEstablished,
  connectionClosed,
  connectionError,
  newTransactionReceived,
  RealtimeTransaction,
} from '@/store/slices/realtimeTransactionsSlice';
import { selectMonitoredWallets } from '@/store/selectors/walletsSelectors'; // Updated selector name
import type { MonitoredWalletInfo } from '@/@types/wallet'; // Import the type

// NATS WebSocket URL - typically does not include a path like /ws/transactions
// The NATS server itself handles the WebSocket upgrade on its configured WebSocket port.
const NATS_WS_URL = import.meta.env.VITE_REALTIME_TRANSACTIONS_WS_URL || 'ws://localhost:8080';

let nc: NatsConnection | null = null;
let subscriptions: Subscription[] = []; // To keep track of multiple subscriptions
const sc = StringCodec(); // For decoding NATS message payloads if they are strings
const jc = JSONCodec<RealtimeTransaction>(); // For decoding NATS message payloads if they are JSON

const RealtimeTransactionService = {
  connect: () => {
    if (nc && !nc.isClosed()) {
      console.log('NATS connection already established or connecting.');
      return;
    }

    store.dispatch(connectionInitiated());

    const monitoredWallets = selectMonitoredWallets(store.getState());
    if (!monitoredWallets || monitoredWallets.length === 0) {
      const errMsg = 'No wallet addresses found to monitor.';
      console.warn(errMsg);
      store.dispatch(connectionError(errMsg));
      // We could also dispatch connectionClosed here if we don't want to retry without addresses
      // store.dispatch(connectionClosed('No addresses to monitor'));
      return; // Don't attempt to connect without addresses
    }

    console.log(`Attempting to connect to NATS: ${NATS_WS_URL} for wallets:`, monitoredWallets);
    // NATS connection logic using nats.ws library
    (async () => {
      try {
        nc = await connect({ servers: NATS_WS_URL });
        console.log(`Connected to NATS server: ${nc.getServer()}`);
        store.dispatch(connectionEstablished());

        // Handle NATS connection status updates (optional but good for robust handling)
        (async () => {
          for await (const status of nc.status()) {
            console.info(`NATS connection status: ${status.type}`, status.data);
            // You can dispatch actions based on status type e.g., 'reconnecting', 'error'
            if (status.type === 'error' || status.type === 'disconnect') {
              store.dispatch(connectionError(status.data?.toString() || 'NATS connection issue'));
            }
          }
        })().then(); // Fire and forget for status monitoring

        // Logic to subscribe to wallet addresses
        const currentNc = nc; // Assign to a new const for type narrowing
        if (!currentNc) {    // Check the new const
          console.error('NATS connection not available for subscription.');
          store.dispatch(connectionError('NATS connection lost before subscription.'));
          return;
        }
        monitoredWallets.forEach((wallet: MonitoredWalletInfo) => {
          // Construct subject: e.g., eth.mainnet.transactions.0x123abc...
          const subject = `${wallet.network}.${wallet.subnet}.transactions.${wallet.address}`;
          console.log(`Subscribing to NATS subject: ${subject}`);
          const sub = currentNc.subscribe(subject, {
            callback: (err, msg) => {
              if (err) {
                console.error(`Error in NATS subscription to ${subject} for wallet ${wallet.address}:`, err);
                store.dispatch(connectionError(`Subscription error for ${subject} (${wallet.address}): ${err.message}`));
                return;
              }
              try {
                const transactionData = jc.decode(msg.data);
                console.log(`Received transaction on subject ${msg.subject}:`, transactionData);
                store.dispatch(newTransactionReceived(transactionData));
              } catch (e) {
                console.error('Error parsing incoming NATS message:', e, 'Raw data:', sc.decode(msg.data));
              }
            },
          });
          subscriptions.push(sub);
        });

        // Handle connection closure
        await nc.closed().then((err) => {
          const reason = err ? err.message : 'NATS connection closed.';
          console.log('NATS connection closed event:', reason);
          store.dispatch(connectionClosed(reason));
          nc = null;
          subscriptions = []; // Clear subscriptions as they are no longer valid
        }).catch(err => {
          // This catch is for errors during the nc.closed() promise itself, not for the close event error
          console.error('Error awaiting NATS connection closure:', err);
          store.dispatch(connectionClosed('NATS connection closed with error.'));
          nc = null;
          subscriptions = [];
        });

      } catch (err: any) {
        const errMsg = `Failed to connect to NATS: ${err.message || err.toString()}`;
        console.error(errMsg, err);
        store.dispatch(connectionError(errMsg));
        // Ensure nc is null if connection failed
        if (nc && !nc.isClosed()) {
          await nc.close().catch(closeErr => console.error('Error closing NATS during connect error:', closeErr));
        }
        nc = null;
        subscriptions = [];
      }
    })();
  },

  disconnect: async () => { // Made async for nc.close() or nc.drain()
    if (nc) {
      console.log('Disconnecting NATS...');
      try {
        await nc.close(); // Gracefully close the connection
        // nc.drain() could also be used if you want to process inflight messages before closing
        console.log('NATS connection closed by disconnect call.');
      } catch (err) {
        console.error('Error closing NATS connection:', err);
      }
      // The closed handler (if set up via nc.closed().then(...)) should also dispatch connectionClosed.
      // If not, we might need to dispatch it here too, but typically the library handles it.
    }
    // nc = null; // This will be handled by the closed event handler
    // subscriptions will also be cleared by the closed event handler or here if needed
  },
  
  // Example: send a message if needed later
  // sendMessage: (message: any) => {
  //   if (socket && socket.readyState === WebSocket.OPEN) {
  //     socket.send(JSON.stringify(message));
  //   } else {
  //     console.error('WebSocket is not connected.');
  //   }
  // }
};

export default RealtimeTransactionService;
