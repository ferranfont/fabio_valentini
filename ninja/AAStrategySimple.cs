#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

// TCP/IP networking
using System.Net.Sockets;
using System.Threading;
using System.IO;

namespace NinjaTrader.NinjaScript.Strategies
{
    public class AAStrategySimple : Strategy
    {
        // TCP connection for bidirectional communication
        private TcpClient tcpClient;
        private NetworkStream networkStream;
        private StreamReader reader;
        private bool isConnected = false;
        private object sendLock = new object();
        private int ticksSent = 0;
        private int connectionAttempts = 0;
        private Thread listenerThread;

        // Order management
        private Order entryOrder = null;
        private Order takeProfitOrder = null;
        private Order stopLossOrder = null;
        private bool waitingForFill = false;
        private string pendingDirection = "";
        private int signalCounter = 0;
        private double entryPrice = 0.0;
        private object lockObject = new object();

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Simple strategy - sends ticks, receives signals, executes LIMIT orders with TP/SL";
                Name = "AAStrategySimple";
                Calculate = Calculate.OnEachTick;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = true;  // Fill LIMIT orders when price touches (not crosses)
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = true;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 20;
                IsInstantiatedOnEachOptimizationIteration = true;
                IsOverlay = true;

                // Connection parameters
                ServerHost = "127.0.0.1";
                ServerPort = 55555;  // Port for receiving signals from tick_server_bidirect.py
                MaxConnectionAttempts = 10;
                ReconnectDelaySeconds = 5;

                // Trading parameters
                TakeProfitTicks = 16;  // 4 points
                StopLossTicks = 12;    // 3 points
                LimitOffsetTicks = 0;  // LIMIT order at market price (Bid for LONG, Ask for SHORT)
                Quantity = 1;
            }
            else if (State == State.Configure)
            {
            }
            else if (State == State.DataLoaded)
            {
                ConnectToServer();

                if (isConnected)
                {
                    string msg = string.Format("[AAStrategySimple] Connected to {0}:{1}", ServerHost, ServerPort);
                    Print(msg);
                    Draw.TextFixed(this, "status", msg + "\nTicks sent: 0", TextPosition.TopLeft);
                }
                else
                {
                    string msg = string.Format("[AAStrategySimple] FAILED to connect to {0}:{1}", ServerHost, ServerPort);
                    Print(msg);
                    Draw.TextFixed(this, "status", msg, TextPosition.TopLeft);
                }
            }
            else if (State == State.Realtime)
            {
                if (!isConnected)
                    ConnectToServer();
            }
            else if (State == State.Terminated)
            {
                isConnected = false;

                if (listenerThread != null && listenerThread.IsAlive)
                {
                    listenerThread.Join(1000);
                }

                SendCompletionSignal();
                Thread.Sleep(500);

                DisconnectFromServer();

                Print(string.Format("[AAStrategySimple] Disconnected. Total ticks sent: {0}", ticksSent));
            }
        }

        private void ConnectToServer()
        {
            connectionAttempts = 0;

            while (connectionAttempts < MaxConnectionAttempts && !isConnected)
            {
                try
                {
                    connectionAttempts++;
                    Print(string.Format("[AAStrategySimple] Connection attempt {0}/{1}...", connectionAttempts, MaxConnectionAttempts));

                    tcpClient = new TcpClient();
                    tcpClient.Connect(ServerHost, ServerPort);
                    networkStream = tcpClient.GetStream();
                    reader = new StreamReader(networkStream, Encoding.UTF8);
                    isConnected = true;

                    Print("[AAStrategySimple] Connection successful!");

                    // Start listener thread
                    listenerThread = new Thread(ListenForSignals);
                    listenerThread.IsBackground = true;
                    listenerThread.Start();

                    break;
                }
                catch (Exception ex)
                {
                    Print(string.Format("[AAStrategySimple] Connection attempt {0} failed: {1}", connectionAttempts, ex.Message));

                    if (connectionAttempts < MaxConnectionAttempts)
                    {
                        Print(string.Format("[AAStrategySimple] Waiting {0} seconds before retry...", ReconnectDelaySeconds));
                        Thread.Sleep(ReconnectDelaySeconds * 1000);
                    }
                }
            }

            if (!isConnected)
            {
                Print(string.Format("[AAStrategySimple] Failed to connect after {0} attempts.", MaxConnectionAttempts));
            }
        }

        private void ListenForSignals()
        {
            while (isConnected)
            {
                try
                {
                    string line = reader.ReadLine();
                    if (line == null)
                    {
                        Print("[AAStrategySimple] Server closed connection");
                        isConnected = false;
                        break;
                    }

                    ProcessSignal(line);
                }
                catch (Exception ex)
                {
                    if (isConnected)
                    {
                        Print(string.Format("[AAStrategySimple] Error reading from server: {0}", ex.Message));
                    }
                    break;
                }
            }
        }

        private void ProcessSignal(string json)
        {
            try
            {
                if (json.Contains("\"command\"") && json.Contains("\"PATTERN\""))
                {
                    string shape = "";
                    double signalPrice = 0.0;

                    // Extract shape
                    if (json.Contains("\"d_shape\""))
                        shape = "d_shape";
                    else if (json.Contains("\"p_shape\""))
                        shape = "p_shape";

                    // Extract price from JSON (e.g., "price":20515.50)
                    int priceIndex = json.IndexOf("\"price\":");
                    if (priceIndex >= 0)
                    {
                        int startIndex = priceIndex + 8; // Skip "price":
                        int endIndex = json.IndexOfAny(new char[] { ',', '}' }, startIndex);
                        if (endIndex > startIndex)
                        {
                            string priceStr = json.Substring(startIndex, endIndex - startIndex).Trim();
                            double.TryParse(priceStr, System.Globalization.NumberStyles.Any,
                                System.Globalization.CultureInfo.InvariantCulture, out signalPrice);
                        }
                    }

                    // Fallback to Close[0] if price not found
                    if (signalPrice == 0.0)
                        signalPrice = Close[0];

                    if (!string.IsNullOrEmpty(shape))
                    {
                        lock (lockObject)
                        {
                            if (Position.MarketPosition == MarketPosition.Flat && !waitingForFill)
                            {
                                string direction = (shape == "d_shape") ? "LONG" : "SHORT";
                                pendingDirection = direction;
                                waitingForFill = true;

                                signalCounter++;
                                Print(string.Format("[AAStrategySimple] Received {0} signal -> {1} entry (#{2}) @ {3:F2}",
                                    shape, direction, signalCounter, signalPrice));

                                // Draw pattern dot using SIGNAL PRICE (not Close[0])
                                string dotTag = "Pattern_" + signalCounter;

                                if (shape == "d_shape")
                                {
                                    // d_shape = BID absorption -> LONG -> RED dot at signal price
                                    TriggerCustomEvent(o => Draw.Dot(this, dotTag, true, 0, signalPrice, Brushes.Red), 0);
                                    Print(string.Format("[AAStrategySimple] Drew RED dot at {0:F2} (signal price)", signalPrice));
                                }
                                else
                                {
                                    // p_shape = ASK absorption -> SHORT -> GREEN dot at signal price
                                    TriggerCustomEvent(o => Draw.Dot(this, dotTag, true, 0, signalPrice, Brushes.Lime), 0);
                                    Print(string.Format("[AAStrategySimple] Drew GREEN dot at {0:F2} (signal price)", signalPrice));
                                }

                                // Place entry order (MARKET if offset < 0, LIMIT otherwise)
                                // Include pattern number in order name for tracking
                                string entryOrderName = string.Format("{0}_ENTRY_#{1}", direction, signalCounter);

                                if (direction == "LONG")
                                {
                                    if (LimitOffsetTicks < 0)
                                    {
                                        // Use MARKET order for guaranteed fill
                                        entryOrder = EnterLong(Quantity, entryOrderName);
                                        Print(string.Format("[AAStrategySimple] LONG MARKET #{0} (offset < 0)", signalCounter));
                                    }
                                    else
                                    {
                                        // Use LIMIT order
                                        double limitPrice = GetCurrentBid() - (LimitOffsetTicks * TickSize);
                                        entryOrder = EnterLongLimit(limitPrice, entryOrderName);
                                        Print(string.Format("[AAStrategySimple] LONG LIMIT #{0} @ {1:F2}", signalCounter, limitPrice));
                                    }
                                }
                                else
                                {
                                    if (LimitOffsetTicks < 0)
                                    {
                                        // Use MARKET order for guaranteed fill
                                        entryOrder = EnterShort(Quantity, entryOrderName);
                                        Print(string.Format("[AAStrategySimple] SHORT MARKET #{0} (offset < 0)", signalCounter));
                                    }
                                    else
                                    {
                                        // Use LIMIT order
                                        double limitPrice = GetCurrentAsk() + (LimitOffsetTicks * TickSize);
                                        entryOrder = EnterShortLimit(limitPrice, entryOrderName);
                                        Print(string.Format("[AAStrategySimple] SHORT LIMIT #{0} @ {1:F2}", signalCounter, limitPrice));
                                    }
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Print(string.Format("[AAStrategySimple] Error processing signal: {0}", ex.Message));
            }
        }

        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice,
            int quantity, int filled, double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string nativeError)
        {
            lock (lockObject)
            {
                // Track entry order cancellations
                if (order == entryOrder)
                {
                    Print(string.Format("[AAStrategySimple] Entry Order Update: {0} | State: {1} | Error: {2}",
                        order.Name, orderState, error));

                    // If entry order cancelled/rejected, reset waitingForFill
                    if (orderState == OrderState.Cancelled || orderState == OrderState.Rejected)
                    {
                        Print(string.Format("[AAStrategySimple] Entry order {0}, resetting flags", orderState));
                        waitingForFill = false;
                        pendingDirection = "";
                        entryOrder = null;
                    }
                }
            }
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId,
            double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            lock (lockObject)
            {
                if (execution.Order == null || execution.Order.OrderState != OrderState.Filled)
                    return;

                string orderName = execution.Order.Name;

                Print(string.Format("[AAStrategySimple] Execution FILLED: {0} @ {1:F2}", orderName, price));

                // Check if ENTRY order filled (use name matching instead of object reference)
                if (waitingForFill && (orderName.StartsWith("LONG_ENTRY_#") || orderName.StartsWith("SHORT_ENTRY_#")))
                {
                    entryPrice = price;
                    Print(string.Format("[AAStrategySimple] *** ENTRY FILLED {0} at {1:F2}, placing TP/SL ***", orderName, price));

                    // NO draw entry fill triangle - removed for cleaner chart
                    // string triangleTag = "EntryFill_" + signalCounter;
                    // if (pendingDirection == "LONG")
                    // {
                    //     double triPrice = price - 3 * TickSize;
                    //     TriggerCustomEvent(o => Draw.TriangleUp(this, triangleTag, true, 0, triPrice, Brushes.LimeGreen), 0);
                    // }
                    // else
                    // {
                    //     double triPrice = price + 3 * TickSize;
                    //     TriggerCustomEvent(o => Draw.TriangleDown(this, triangleTag, true, 0, triPrice, Brushes.OrangeRed), 0);
                    // }

                    // Place TP/SL bracket (OCO) - include pattern number
                    string tpOrderName = string.Format("TP_{0}_#{1}", pendingDirection, signalCounter);
                    string slOrderName = string.Format("SL_{0}_#{1}", pendingDirection, signalCounter);
                    string fromEntryOrderName = string.Format("{0}_ENTRY_#{1}", pendingDirection, signalCounter);

                    if (pendingDirection == "LONG")
                    {
                        double tpPrice = price + (TakeProfitTicks * TickSize);
                        double slPrice = price - (StopLossTicks * TickSize);

                        Print(string.Format("[AAStrategySimple] Placing TP @ {0:F2}, SL @ {1:F2} for #{2}", tpPrice, slPrice, signalCounter));

                        takeProfitOrder = ExitLongLimit(0, true, Quantity, tpPrice, tpOrderName, fromEntryOrderName);
                        stopLossOrder = ExitLongStopMarket(0, true, Quantity, slPrice, slOrderName, fromEntryOrderName);
                    }
                    else
                    {
                        double tpPrice = price - (TakeProfitTicks * TickSize);
                        double slPrice = price + (StopLossTicks * TickSize);

                        Print(string.Format("[AAStrategySimple] Placing TP @ {0:F2}, SL @ {1:F2} for #{2}", tpPrice, slPrice, signalCounter));

                        takeProfitOrder = ExitShortLimit(0, true, Quantity, tpPrice, tpOrderName, fromEntryOrderName);
                        stopLossOrder = ExitShortStopMarket(0, true, Quantity, slPrice, slOrderName, fromEntryOrderName);
                    }

                    waitingForFill = false;
                    pendingDirection = "";
                }
                // Check if EXIT order filled (TP or SL)
                else if (orderName.StartsWith("TP_") || orderName.StartsWith("SL_"))
                {
                    string exitTag = orderName.StartsWith("TP_") ? "TARGET" : "STOP";
                    Print(string.Format("[AAStrategySimple] *** EXIT FILLED {0} at {1:F2} ({2}) ***", orderName, price, exitTag));

                    // Extract pattern number from order name (e.g., "TP_LONG_#12" -> "12")
                    string patternNum = "unknown";
                    int hashIndex = orderName.IndexOf("#");
                    if (hashIndex >= 0 && hashIndex < orderName.Length - 1)
                    {
                        patternNum = orderName.Substring(hashIndex + 1);
                    }

                    // Draw exit diamond (thread-safe)
                    string diamondTag = "Exit_" + patternNum;
                    if (exitTag == "TARGET")
                    {
                        TriggerCustomEvent(o => Draw.Diamond(this, diamondTag, true, 0, price, Brushes.LimeGreen), 0);
                    }
                    else
                    {
                        TriggerCustomEvent(o => Draw.Diamond(this, diamondTag, true, 0, price, Brushes.Red), 0);
                    }

                    // Send exit to Python (include pattern number)
                    SendExitToServer(price, exitTag, patternNum);

                    // Reset all order references for next trade
                    entryOrder = null;
                    takeProfitOrder = null;
                    stopLossOrder = null;
                }
            }
        }

        private void SendExitToServer(double price, string tag, string patternNum)
        {
            try
            {
                string json = string.Format("{{\"command\":\"EXIT\",\"price\":{0},\"tag\":\"{1}\",\"pattern\":\"#{2}\"}}",
                    price.ToString(System.Globalization.CultureInfo.InvariantCulture), tag, patternNum);
                SendMessage(json);
                Print(string.Format("[AAStrategySimple] Sent EXIT to server: {0} #{1} @ {2:F2}", tag, patternNum, price));
            }
            catch (Exception ex)
            {
                Print(string.Format("[AAStrategySimple] Error sending exit: {0}", ex.Message));
            }
        }

        private void DisconnectFromServer()
        {
            try
            {
                if (reader != null)
                {
                    reader.Close();
                    reader.Dispose();
                    reader = null;
                }

                if (networkStream != null)
                {
                    networkStream.Close();
                    networkStream.Dispose();
                    networkStream = null;
                }

                if (tcpClient != null)
                {
                    tcpClient.Close();
                    tcpClient = null;
                }

                isConnected = false;
            }
            catch (Exception ex)
            {
                Print(string.Format("[AAStrategySimple] Error disconnecting: {0}", ex.Message));
            }
        }

        protected override void OnBarUpdate()
        {
            // Not used
        }

        protected override void OnMarketData(MarketDataEventArgs marketDataUpdate)
        {
            if (!isConnected)
                return;

            try
            {
                if (marketDataUpdate.Price <= 0 || marketDataUpdate.Volume <= 0)
                    return;

                string side = "UNKNOWN";
                if (marketDataUpdate.Price >= marketDataUpdate.Ask)
                    side = "ASK";
                else if (marketDataUpdate.Price <= marketDataUpdate.Bid)
                    side = "BID";
                else
                    side = "BETWEEN";

                string timestamp = marketDataUpdate.Time.ToString("yyyy-MM-ddTHH:mm:ss.fff");

                string json = string.Format(
                    "{{\"timestamp\":\"{0}\",\"price\":{1},\"volume\":{2},\"side\":\"{3}\"}}",
                    timestamp,
                    marketDataUpdate.Price.ToString(System.Globalization.CultureInfo.InvariantCulture),
                    marketDataUpdate.Volume,
                    side
                );

                SendMessage(json);

                ticksSent++;

                if (ticksSent % 1000 == 0)
                {
                    string msg = string.Format("[AAStrategySimple] {0}:{1} | Ticks: {2:N0} | Patterns: {3}",
                        ServerHost, ServerPort, ticksSent, signalCounter);
                    Draw.TextFixed(this, "status", msg, TextPosition.TopLeft);
                }
            }
            catch (Exception ex)
            {
                Print(string.Format("[AAStrategySimple] Error processing tick: {0}", ex.Message));
            }
        }

        private void SendMessage(string message)
        {
            if (!isConnected || networkStream == null)
                return;

            lock (sendLock)
            {
                try
                {
                    byte[] data = Encoding.UTF8.GetBytes(message + "\n");
                    networkStream.Write(data, 0, data.Length);
                    networkStream.Flush();
                }
                catch (Exception ex)
                {
                    Print(string.Format("[AAStrategySimple] Error sending: {0}", ex.Message));
                    isConnected = false;
                    DisconnectFromServer();
                    ConnectToServer();
                }
            }
        }

        private void SendCompletionSignal()
        {
            try
            {
                string json = "{\"command\":\"COMPLETE\"}";
                SendMessage(json);
                Print("[AAStrategySimple] Sent completion signal");
            }
            catch (Exception ex)
            {
                Print(string.Format("[AAStrategySimple] Error sending completion: {0}", ex.Message));
            }
        }

        #region Properties

        [NinjaScriptProperty]
        [Display(Name = "Server Host", Order = 1, GroupName = "Connection")]
        public string ServerHost { get; set; }

        [NinjaScriptProperty]
        [Range(1, 65535)]
        [Display(Name = "Server Port", Order = 2, GroupName = "Connection")]
        public int ServerPort { get; set; }

        [Range(1, 100)]
        [Display(Name = "Max Connection Attempts", Order = 3, GroupName = "Connection")]
        public int MaxConnectionAttempts { get; set; }

        [Range(1, 60)]
        [Display(Name = "Reconnect Delay (seconds)", Order = 4, GroupName = "Connection")]
        public int ReconnectDelaySeconds { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Take Profit (ticks)", Order = 1, GroupName = "Trading")]
        public int TakeProfitTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Stop Loss (ticks)", Order = 2, GroupName = "Trading")]
        public int StopLossTicks { get; set; }

        [NinjaScriptProperty]
        [Range(-5, 10)]
        [Display(Name = "Limit Offset (ticks)", Description = "Ticks better/worse than market (-1=cross spread, 0=at market, 1=better)", Order = 3, GroupName = "Trading")]
        public int LimitOffsetTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Quantity", Order = 4, GroupName = "Trading")]
        public int Quantity { get; set; }

        #endregion
    }
}
