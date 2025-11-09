#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
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
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;

// TCP/IP networking
using System.Net.Sockets;
using System.Threading;
using System.IO;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class AAStrategyBidirect : Strategy
    {
        private TcpClient tcpClient;
        private NetworkStream networkStream;
        private StreamReader reader;
        private bool isConnected = false;
        private Thread listenerThread;
        private object lockObject = new object();

        // Order tracking
        private Order entryOrder = null;
        private Order stopLossOrder = null;
        private Order takeProfitOrder = null;
        private bool waitingForFill = false;
        private string pendingDirection = "";  // "LONG" or "SHORT"

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description                                 = @"Bidirectional strategy - receives signals from Python server";
                Name                                        = "AAStrategyBidirect";
                Calculate                                   = Calculate.OnBarClose;
                EntriesPerDirection                         = 1;
                EntryHandling                               = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy                = true;
                ExitOnSessionCloseSeconds                   = 30;
                IsFillLimitOnTouch                          = false;
                MaximumBarsLookBack                         = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution                         = OrderFillResolution.Standard;
                Slippage                                    = 0;
                StartBehavior                               = StartBehavior.WaitUntilFlat;
                TimeInForce                                 = TimeInForce.Gtc;
                TraceOrders                                 = true;
                RealtimeErrorHandling                       = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling                          = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade                         = 20;
                IsInstantiatedOnEachOptimizationIteration   = true;

                // Parameters
                ServerHost                                  = "127.0.0.1";
                ServerPort                                  = 55556;  // Different port from tick sender
                TakeProfitTicks                             = 16;     // 4 points * 4 ticks/point = 16 ticks
                StopLossTicks                               = 12;     // 3 points * 4 ticks/point = 12 ticks
                Quantity                                    = 1;
            }
            else if (State == State.Configure)
            {
            }
            else if (State == State.DataLoaded)
            {
                // Connect when data is loaded (works for both Realtime and Historical)
                ConnectToServer();
            }
            else if (State == State.Realtime)
            {
                // Already connected in DataLoaded, but reconnect if needed
                if (!isConnected)
                    ConnectToServer();
            }
            else if (State == State.Terminated)
            {
                DisconnectFromServer();
            }
        }

        private void ConnectToServer()
        {
            try
            {
                tcpClient = new TcpClient();
                tcpClient.Connect(ServerHost, ServerPort);
                networkStream = tcpClient.GetStream();
                reader = new StreamReader(networkStream, Encoding.UTF8);
                isConnected = true;

                Print(string.Format("[AAStrategyBidirect] Connected to {0}:{1}", ServerHost, ServerPort));

                // Start listener thread
                listenerThread = new Thread(ListenForSignals);
                listenerThread.IsBackground = true;
                listenerThread.Start();
            }
            catch (Exception ex)
            {
                Print(string.Format("[AAStrategyBidirect] Failed to connect: {0}", ex.Message));
                isConnected = false;
            }
        }

        private void DisconnectFromServer()
        {
            isConnected = false;

            try
            {
                if (reader != null)
                {
                    reader.Close();
                    reader.Dispose();
                }

                if (networkStream != null)
                {
                    networkStream.Close();
                    networkStream.Dispose();
                }

                if (tcpClient != null)
                {
                    tcpClient.Close();
                }

                if (listenerThread != null && listenerThread.IsAlive)
                {
                    listenerThread.Join(1000); // Wait up to 1 second
                }

                Print("[AAStrategyBidirect] Disconnected from server");
            }
            catch (Exception ex)
            {
                Print(string.Format("[AAStrategyBidirect] Error disconnecting: {0}", ex.Message));
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
                        Print("[AAStrategyBidirect] Server closed connection");
                        isConnected = false;
                        break;
                    }

                    ProcessSignal(line);
                }
                catch (Exception ex)
                {
                    if (isConnected)
                    {
                        Print(string.Format("[AAStrategyBidirect] Error reading from server: {0}", ex.Message));
                    }
                    break;
                }
            }
        }

        private void ProcessSignal(string json)
        {
            try
            {
                // Simple JSON parsing (looking for "command" and "type" fields)
                if (json.Contains("\"command\""))
                {
                    if (json.Contains("\"PATTERN\""))
                    {
                        // Extract shape: d_shape or p_shape
                        string shape = "";
                        if (json.Contains("\"d_shape\""))
                            shape = "d_shape";
                        else if (json.Contains("\"p_shape\""))
                            shape = "p_shape";

                        if (!string.IsNullOrEmpty(shape))
                        {
                            lock (lockObject)
                            {
                                if (Position.MarketPosition == MarketPosition.Flat && !waitingForFill)
                                {
                                    // d_shape -> LONG, p_shape -> SHORT
                                    string direction = (shape == "d_shape") ? "LONG" : "SHORT";
                                    pendingDirection = direction;
                                    waitingForFill = true;

                                    Print(string.Format("[AAStrategyBidirect] Received {0} signal -> {1} entry",
                                        shape, direction));

                                    // Enter position
                                    if (direction == "LONG")
                                    {
                                        entryOrder = EnterLong(Quantity, "LONG_ENTRY");
                                    }
                                    else
                                    {
                                        entryOrder = EnterShort(Quantity, "SHORT_ENTRY");
                                    }
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Print(string.Format("[AAStrategyBidirect] Error processing signal: {0}", ex.Message));
            }
        }

        protected override void OnBarUpdate()
        {
            // Strategy logic handled in ProcessSignal and OnExecutionUpdate
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId,
            double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            lock (lockObject)
            {
                // Log all executions for debugging
                Print(string.Format("[AAStrategyBidirect] Execution: {0} | Order: {1} | State: {2} | Price: {3}",
                    execution.Name,
                    execution.Order != null ? execution.Order.Name : "NULL",
                    execution.Order != null ? execution.Order.OrderState.ToString() : "NULL",
                    price));

                // Check if this is our entry order being filled
                if (execution.Order != null && execution.Order == entryOrder && waitingForFill)
                {
                    if (execution.Order.OrderState == OrderState.Filled)
                    {
                        Print(string.Format("[AAStrategyBidirect] *** ENTRY FILLED at {0}, placing TP/SL ***", price));

                        // NOW place TP and SL orders
                        if (pendingDirection == "LONG")
                        {
                            Print(string.Format("[AAStrategyBidirect] Setting LONG TP/SL: TP={0} ticks, SL={1} ticks",
                                TakeProfitTicks, StopLossTicks));

                            // For LONG: TP above, SL below
                            SetProfitTarget("LONG_ENTRY", CalculationMode.Ticks, TakeProfitTicks);
                            SetStopLoss("LONG_ENTRY", CalculationMode.Ticks, StopLossTicks, false);
                        }
                        else if (pendingDirection == "SHORT")
                        {
                            Print(string.Format("[AAStrategyBidirect] Setting SHORT TP/SL: TP={0} ticks, SL={1} ticks",
                                TakeProfitTicks, StopLossTicks));

                            // For SHORT: TP below, SL above
                            SetProfitTarget("SHORT_ENTRY", CalculationMode.Ticks, TakeProfitTicks);
                            SetStopLoss("SHORT_ENTRY", CalculationMode.Ticks, StopLossTicks, false);
                        }

                        waitingForFill = false;
                        pendingDirection = "";
                    }
                }

                // Check for exit executions (TP or SL hit)
                if (execution.Order != null &&
                    (execution.Order.OrderType == OrderType.Limit || execution.Order.OrderType == OrderType.StopMarket))
                {
                    if (execution.Order.OrderState == OrderState.Filled)
                    {
                        string exitTag = execution.Order.OrderType == OrderType.Limit ? "TARGET" : "STOP";
                        Print(string.Format("[AAStrategyBidirect] *** EXIT FILLED at {0} ({1}) ***", price, exitTag));

                        // Send exit info to Python server
                        SendExitToServer(price, exitTag);
                    }
                }
            }
        }

        private void SendExitToServer(double price, string tag)
        {
            if (!isConnected || networkStream == null)
                return;

            try
            {
                string json = string.Format(
                    "{{\"command\":\"EXIT\",\"price\":{0},\"tag\":\"{1}\",\"timestamp\":\"{2}\"}}",
                    price.ToString(System.Globalization.CultureInfo.InvariantCulture),
                    tag,
                    DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss.fff")
                );

                byte[] data = Encoding.UTF8.GetBytes(json + "\n");
                networkStream.Write(data, 0, data.Length);
                networkStream.Flush();

                Print(string.Format("[AAStrategyBidirect] Sent EXIT to server: {0} @ {1}", tag, price));
            }
            catch (Exception ex)
            {
                Print(string.Format("[AAStrategyBidirect] Error sending exit to server: {0}", ex.Message));
            }
        }

        #region Properties

        [NinjaScriptProperty]
        [Display(Name = "Server Host", Description = "Python server hostname/IP", Order = 1, GroupName = "Connection")]
        public string ServerHost { get; set; }

        [NinjaScriptProperty]
        [Range(1, 65535)]
        [Display(Name = "Server Port", Description = "Python server port", Order = 2, GroupName = "Connection")]
        public int ServerPort { get; set; }

        [NinjaScriptProperty]
        [Range(1, 1000)]
        [Display(Name = "Take Profit (ticks)", Description = "Take profit in ticks", Order = 3, GroupName = "Strategy")]
        public int TakeProfitTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, 1000)]
        [Display(Name = "Stop Loss (ticks)", Description = "Stop loss in ticks", Order = 4, GroupName = "Strategy")]
        public int StopLossTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Quantity", Description = "Order quantity", Order = 5, GroupName = "Strategy")]
        public int Quantity { get; set; }

        #endregion
    }
}
