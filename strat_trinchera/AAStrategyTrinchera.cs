// AAStrategyTrinchera - NinjaTrader Strategy for Trinchera Live Trading
//
// PURPOSE:
// Sends real-time tick data to Python (tick_server_trinchera_bidirect.py)
// Receives order commands from Python and executes them
//
// PORTS:
// - 5555: Sends tick data TO Python
// - 5556: Receives order commands FROM Python
//
// USAGE:
// 1. Apply this strategy to your NQ chart in NinjaTrader
// 2. Run: python tick_server_trinchera_bidirect.py
// 3. Strategy will automatically connect and start sending ticks
//
// DIFFERENCES FROM AAStrategyBiderect:
// - Uses ports 5555/5556 (instead of 5553/5554)
// - Designed for Trinchera strategy (big volume + mean reversion)
// - Can run simultaneously with AAStrategyBiderect on different chart

#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class AAStrategyTrinchera : Strategy
    {
        // ============================================================================
        // NETWORK CONFIGURATION
        // ============================================================================
        private const int TICK_SEND_PORT = 5555;        // Port to SEND tick data TO Python
        private const int ORDER_RECEIVE_PORT = 5556;    // Port to RECEIVE orders FROM Python

        // Socket connections
        private TcpListener tickDataServer;             // Server for sending tick data
        private TcpClient tickDataClient;               // Client connection for tick data
        private NetworkStream tickDataStream;
        private StreamWriter tickDataWriter;

        private TcpListener orderReceiveServer;         // Server for receiving orders
        private TcpClient orderReceiveClient;           // Client connection for orders
        private NetworkStream orderReceiveStream;
        private StreamReader orderReceiveReader;
        private Thread orderReceiveThread;

        // Connection state
        private bool isConnected = false;
        private bool shouldStop = false;

        // ============================================================================
        // STRATEGY INITIALIZATION
        // ============================================================================
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Trinchera Live Trading - Bidirectional NinjaTrader Integration";
                Name = "AAStrategyTrinchera";
                Calculate = Calculate.OnEachTick;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 1;
                IsInstantiatedOnEachOptimizationIteration = true;
            }
            else if (State == State.Configure)
            {
                // Strategy configuration
            }
            else if (State == State.DataLoaded)
            {
                Print("═══════════════════════════════════════════════════════════");
                Print("AAStrategyTrinchera - Initializing");
                Print("═══════════════════════════════════════════════════════════");
                Print("Tick Data Server Port: " + TICK_SEND_PORT);
                Print("Order Receive Port: " + ORDER_RECEIVE_PORT);
                Print("═══════════════════════════════════════════════════════════");

                // Start network servers
                StartTickDataServer();
                StartOrderReceiveServer();
            }
            else if (State == State.Terminated)
            {
                Print("═══════════════════════════════════════════════════════════");
                Print("AAStrategyTrinchera - Shutting Down");
                Print("═══════════════════════════════════════════════════════════");

                shouldStop = true;

                // Clean up connections
                CloseConnections();
            }
        }

        // ============================================================================
        // TICK DATA SERVER (SENDS TO PYTHON)
        // ============================================================================
        private void StartTickDataServer()
        {
            try
            {
                tickDataServer = new TcpListener(IPAddress.Any, TICK_SEND_PORT);
                tickDataServer.Start();
                Print("[OK] Tick data server started on port " + TICK_SEND_PORT);
                Print("[INFO] Waiting for Python connection...");

                // Accept connection asynchronously
                tickDataServer.BeginAcceptTcpClient(OnTickDataClientConnected, null);
            }
            catch (Exception ex)
            {
                Print("[ERROR] Failed to start tick data server: " + ex.Message);
            }
        }

        private void OnTickDataClientConnected(IAsyncResult ar)
        {
            try
            {
                tickDataClient = tickDataServer.EndAcceptTcpClient(ar);
                tickDataStream = tickDataClient.GetStream();
                tickDataWriter = new StreamWriter(tickDataStream) { AutoFlush = true };

                isConnected = true;
                Print("[SUCCESS] Python connected for tick data!");
                Print("═══════════════════════════════════════════════════════════");
                Print("LIVE TRADING ACTIVE - Sending tick data to Python");
                Print("═══════════════════════════════════════════════════════════");
            }
            catch (Exception ex)
            {
                Print("[ERROR] Tick data client connection failed: " + ex.Message);
                isConnected = false;
            }
        }

        // ============================================================================
        // ORDER RECEIVE SERVER (RECEIVES FROM PYTHON)
        // ============================================================================
        private void StartOrderReceiveServer()
        {
            try
            {
                orderReceiveServer = new TcpListener(IPAddress.Any, ORDER_RECEIVE_PORT);
                orderReceiveServer.Start();
                Print("[OK] Order receive server started on port " + ORDER_RECEIVE_PORT);

                // Start thread to listen for orders
                orderReceiveThread = new Thread(OrderReceiveLoop);
                orderReceiveThread.IsBackground = true;
                orderReceiveThread.Start();
            }
            catch (Exception ex)
            {
                Print("[ERROR] Failed to start order receive server: " + ex.Message);
            }
        }

        private void OrderReceiveLoop()
        {
            try
            {
                Print("[INFO] Waiting for Python connection (orders)...");
                orderReceiveClient = orderReceiveServer.AcceptTcpClient();
                orderReceiveStream = orderReceiveClient.GetStream();
                orderReceiveReader = new StreamReader(orderReceiveStream);

                Print("[SUCCESS] Python connected for orders!");

                // Listen for orders
                while (!shouldStop)
                {
                    try
                    {
                        string orderMessage = orderReceiveReader.ReadLine();
                        if (!string.IsNullOrEmpty(orderMessage))
                        {
                            ProcessOrderMessage(orderMessage);
                        }
                    }
                    catch (IOException)
                    {
                        // Connection lost
                        Print("[WARNING] Python connection lost. Reconnecting...");
                        Thread.Sleep(1000);

                        // Try reconnect
                        try
                        {
                            orderReceiveClient = orderReceiveServer.AcceptTcpClient();
                            orderReceiveStream = orderReceiveClient.GetStream();
                            orderReceiveReader = new StreamReader(orderReceiveStream);
                            Print("[SUCCESS] Python reconnected!");
                        }
                        catch
                        {
                            // Reconnection failed, will retry on next iteration
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Print("[ERROR] Order receive loop error: " + ex.Message);
            }
        }

        // ============================================================================
        // TICK DATA PROCESSING
        // ============================================================================
        protected override void OnBarUpdate()
        {
            // Only send on real-time ticks
            if (State != State.Realtime)
                return;

            if (!isConnected || tickDataWriter == null)
                return;

            try
            {
                // Format: TIMESTAMP;PRICE;VOLUME;SIDE;BID;ASK
                // Example: 2025-12-01 14:30:25.123;20500.25;50;BUY;20500.00;20500.50

                string timestamp = Time[0].ToString("yyyy-MM-dd HH:mm:ss.fff");
                double price = Close[0];
                long volume = (long)Volume[0];
                string side = Close[0] >= Open[0] ? "BUY" : "SELL";
                double bid = GetCurrentBid();
                double ask = GetCurrentAsk();

                string tickData = string.Format("{0};{1:F2};{2};{3};{4:F2};{5:F2}",
                    timestamp, price, volume, side, bid, ask);

                tickDataWriter.WriteLine(tickData);
            }
            catch (IOException)
            {
                // Connection lost
                Print("[WARNING] Lost connection to Python. Reconnecting...");
                isConnected = false;

                // Try to reconnect
                try
                {
                    CloseTickDataConnection();
                    tickDataServer.BeginAcceptTcpClient(OnTickDataClientConnected, null);
                }
                catch
                {
                    // Will retry later
                }
            }
            catch (Exception ex)
            {
                Print("[ERROR] Failed to send tick data: " + ex.Message);
            }
        }

        // ============================================================================
        // ORDER PROCESSING (FROM PYTHON)
        // ============================================================================
        private void ProcessOrderMessage(string message)
        {
            try
            {
                Print("[RECEIVED] Order from Python: " + message);

                // Parse JSON message
                // Expected format: {"action":"ENTRY","side":"LONG","contracts":1,"entry_price":20500.25,"tp_price":20505.25,"sl_price":20491.25}

                // Simple JSON parsing (alternatively use JSON.NET library)
                var action = ExtractJsonValue(message, "action");

                if (action == "ENTRY")
                {
                    var side = ExtractJsonValue(message, "side");
                    var contracts = int.Parse(ExtractJsonValue(message, "contracts"));
                    var entryPrice = double.Parse(ExtractJsonValue(message, "entry_price"));
                    var tpPrice = double.Parse(ExtractJsonValue(message, "tp_price"));
                    var slPrice = double.Parse(ExtractJsonValue(message, "sl_price"));

                    ExecuteEntryOrder(side, contracts, entryPrice, tpPrice, slPrice);
                }
                else if (action == "EXIT")
                {
                    var side = ExtractJsonValue(message, "side");
                    var contracts = int.Parse(ExtractJsonValue(message, "contracts"));
                    var exitPrice = double.Parse(ExtractJsonValue(message, "exit_price"));
                    var exitReason = ExtractJsonValue(message, "exit_reason");

                    ExecuteExitOrder(side, contracts, exitPrice, exitReason);
                }
            }
            catch (Exception ex)
            {
                Print("[ERROR] Failed to process order: " + ex.Message);
            }
        }

        private void ExecuteEntryOrder(string side, int contracts, double entryPrice, double tpPrice, double slPrice)
        {
            Print("════════════════════════════════════════════════════════════");
            Print("[ENTRY ORDER] " + side + " " + contracts + " contracts");
            Print("Entry: " + entryPrice + " | TP: " + tpPrice + " | SL: " + slPrice);
            Print("════════════════════════════════════════════════════════════");

            if (side == "LONG")
            {
                EnterLong(contracts, "TrìncheraLong");

                // Set profit target and stop loss
                SetProfitTarget("TrìncheraLong", CalculationMode.Price, tpPrice);
                SetStopLoss("TrìncheraLong", CalculationMode.Price, slPrice, false);
            }
            else if (side == "SHORT")
            {
                EnterShort(contracts, "TrìncheraShort");

                // Set profit target and stop loss
                SetProfitTarget("TrìncheraShort", CalculationMode.Price, tpPrice);
                SetStopLoss("TrìncheraShort", CalculationMode.Price, slPrice, false);
            }
        }

        private void ExecuteExitOrder(string side, int contracts, double exitPrice, string exitReason)
        {
            Print("════════════════════════════════════════════════════════════");
            Print("[EXIT ORDER] " + side + " " + contracts + " contracts");
            Print("Exit: " + exitPrice + " | Reason: " + exitReason);
            Print("════════════════════════════════════════════════════════════");

            if (side == "SELL")
            {
                ExitLong(contracts, "TrìncheraLongExit", "TrìncheraLong");
            }
            else if (side == "BUY")
            {
                ExitShort(contracts, "TrìncheraShortExit", "TrìncheraShort");
            }
        }

        // ============================================================================
        // UTILITY METHODS
        // ============================================================================
        private string ExtractJsonValue(string json, string key)
        {
            // Simple JSON value extraction
            string searchKey = "\"" + key + "\":";
            int startIndex = json.IndexOf(searchKey);

            if (startIndex == -1)
                return "";

            startIndex += searchKey.Length;

            // Skip whitespace
            while (startIndex < json.Length && (json[startIndex] == ' ' || json[startIndex] == '\t'))
                startIndex++;

            // Check if value is string (starts with quote)
            bool isString = json[startIndex] == '"';
            if (isString)
                startIndex++; // Skip opening quote

            int endIndex = startIndex;

            if (isString)
            {
                // Find closing quote
                while (endIndex < json.Length && json[endIndex] != '"')
                    endIndex++;
            }
            else
            {
                // Find comma or closing brace
                while (endIndex < json.Length && json[endIndex] != ',' && json[endIndex] != '}')
                    endIndex++;
            }

            return json.Substring(startIndex, endIndex - startIndex).Trim();
        }

        private void CloseConnections()
        {
            try
            {
                CloseTickDataConnection();
                CloseOrderReceiveConnection();

                if (tickDataServer != null)
                    tickDataServer.Stop();

                if (orderReceiveServer != null)
                    orderReceiveServer.Stop();

                Print("[OK] All connections closed");
            }
            catch (Exception ex)
            {
                Print("[ERROR] Error closing connections: " + ex.Message);
            }
        }

        private void CloseTickDataConnection()
        {
            try
            {
                if (tickDataWriter != null)
                {
                    tickDataWriter.Close();
                    tickDataWriter = null;
                }

                if (tickDataStream != null)
                {
                    tickDataStream.Close();
                    tickDataStream = null;
                }

                if (tickDataClient != null)
                {
                    tickDataClient.Close();
                    tickDataClient = null;
                }

                isConnected = false;
            }
            catch { }
        }

        private void CloseOrderReceiveConnection()
        {
            try
            {
                if (orderReceiveReader != null)
                {
                    orderReceiveReader.Close();
                    orderReceiveReader = null;
                }

                if (orderReceiveStream != null)
                {
                    orderReceiveStream.Close();
                    orderReceiveStream = null;
                }

                if (orderReceiveClient != null)
                {
                    orderReceiveClient.Close();
                    orderReceiveClient = null;
                }
            }
            catch { }
        }
    }
}
