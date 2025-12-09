#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading;
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
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
using System.Net.Sockets;
using System.IO;
#endregion
namespace NinjaTrader.NinjaScript.Strategies
{
    public class AAStrategyTradingLive : Strategy
    {
        // ==============================================================
        // ESTRATEGIA UNMANAGED: Control Total
        // Recibe comandos de Python y gestiona órdenes manualmente
        // CORREGIDO: Ruta CSV original y Dispatcher seguro
        // ==============================================================
        #region Variables
        // TCP Server (Puerto 5557)
        private System.Net.Sockets.TcpListener executionServer;
        private TcpClient executionClient;
        private NetworkStream executionStream;
        private StreamReader executionReader;
        private Thread listenerThread;
        private bool connected = false;
        private bool running = false;
        // Gestión de Órdenes
        private Dictionary<string, OrderInfo> activeOrders;
        private int orderCounter = 0;
        private object orderLock = new object();
        // Variables OCO (Para vincular Buy y Sell del mismo grupo)
        private string currentOcoGroupId = "";
        // CSV Tracking
        private string csvFilePath;
        private object csvLock = new object();
        private DateTime strategyStartTime;
        #endregion
        #region OrderInfo Class
        private class OrderInfo
        {
            public int InternalId { get; set; }
            public string OcoGroupId { get; set; } // ID compartido entre Buy y Sell del mismo comando
            public string Side { get; set; }  // "SELL" or "BUY"
            public double EntryPrice { get; set; }
            public double TpPrice { get; set; }
            public double SlPrice { get; set; }
            public DateTime ExpirationTime { get; set; }
            public DateTime FillTime { get; set; } // Hora de llenado para calcular duración
            
            public Order EntryOrder { get; set; }
            public Order TpOrder { get; set; }
            public Order SlOrder { get; set; }
            
            public bool IsActive { get; set; }
            public bool BothSidesAllowed { get; set; }
        }
        #endregion
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Estrategia UNMANAGED para Trinchera Live";
                Name = "AAStrategyTradingLive";
                Calculate = Calculate.OnEachTick;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.ImmediatelySubmit;
                TimeInForce = TimeInForce.Day;
                TraceOrders = true;
                RealtimeErrorHandling = RealtimeErrorHandling.IgnoreAllErrors;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 1;
                
                // CRÍTICO: Modo Unmanaged activado
                IsUnmanaged = true;
                // Parameters
                ExecutionPort = 5557;
                DefaultQuantity = 1;
            }
            else if (State == State.Configure)
            {
                activeOrders = new Dictionary<string, OrderInfo>();
                // Initialize tracking CSV
                strategyStartTime = DateTime.Now;
                string timestamp = strategyStartTime.ToString("yyyyMMdd_HHmmss");
                
                // RESTAURADA RUTA ORIGINAL
                string outputDir = @"D:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs";
                csvFilePath = Path.Combine(outputDir, string.Format("tracking_record_live_{0}.csv", timestamp));
                
                InitializeCSV();
            }
            else if (State == State.DataLoaded)
            {
                Print("[STRATEGY] DataLoaded - Starting UNMANAGED execution server...");
                StartExecutionServer();
            }
            else if (State == State.Terminated)
            {
                Print("[STRATEGY] Terminated - Disconnecting...");
                DisconnectAll();
            }
        }
        #region CSV Helpers
        private void InitializeCSV()
        {
            try
            {
                // Ensure directory exists
                string directory = Path.GetDirectoryName(csvFilePath);
                if (!Directory.Exists(directory))
                {
                    Print(string.Format("[CSV] Creating directory: {0}", directory));
                    Directory.CreateDirectory(directory);
                }
                
                // Create CSV with headers
                lock (csvLock)
                {
                    using (StreamWriter writer = new StreamWriter(csvFilePath, false))
                    {
                        writer.WriteLine("timestamp,event_type,order_id,action,order_type,price,quantity,status,pnl,exit_reason,duration_sec,current_position,market_price,notes");
                    }
                }
                
                Print(string.Format("[CSV] Tracking file created: {0}", csvFilePath));
            }
            catch (Exception ex)
            {
                Print(string.Format("[CSV] Error initializing: {0}", ex.Message));
            }
        }
        private void WriteToCSV(string eventType, string orderId, string action, string orderType,
            double price, int quantity, string status, double pnl = 0, string exitReason = "",
            double durationSec = 0, string notes = "")
        {
            try
            {
                lock (csvLock)
                {
                    using (StreamWriter writer = new StreamWriter(csvFilePath, true)) // append mode
                    {
                        string timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
                        string currentPos = Position.MarketPosition.ToString();
                        double marketPrice = Close[0];
                        
                        // CSV line
                        string line = string.Format("{0},{1},{2},{3},{4},{5:F2},{6},{7},{8:F2},{9},{10:F3},{11},{12:F2},{13}",
                            timestamp,           // 0
                            eventType,          // 1
                            orderId,            // 2
                            action,             // 3
                            orderType,          // 4
                            price,              // 5
                            quantity,           // 6
                            status,             // 7
                            pnl,                // 8
                            exitReason,         // 9
                            durationSec,        // 10
                            currentPos,         // 11
                            marketPrice,        // 12
                            notes               // 13
                        );
                        
                        writer.WriteLine(line);
                    }
                }
            }
            catch (Exception ex)
            {
                Print(string.Format("[CSV] Write error: {0}", ex.Message));
            }
        }
        private double CalculatePnL(OrderInfo orderInfo, double exitPrice)
        {
            double entryPrice = orderInfo.EntryPrice;
            int quantity = DefaultQuantity;
            double pointValue = 20.0; // NQ point value (Adjust if trading other instruments)
            
            if (orderInfo.Side == "SELL")
            {
                // SHORT: profit when exit price < entry price
                return (entryPrice - exitPrice) * pointValue * quantity;
            }
            else
            {
                // LONG: profit when exit price > entry price
                return (exitPrice - entryPrice) * pointValue * quantity;
            }
        }
        #endregion
        #region Execution Server (Port 5557)
        private void StartExecutionServer()
        {
            try
            {
                executionServer = new System.Net.Sockets.TcpListener(System.Net.IPAddress.Any, ExecutionPort);
                executionServer.Start();
                Print(string.Format("[EXEC SERVER] Started on port {0}, waiting for Python...", ExecutionPort));
                listenerThread = new Thread(ListenForCommands);
                listenerThread.IsBackground = true;
                listenerThread.Start();
                running = true;
            }
            catch (Exception ex)
            {
                Print(string.Format("[EXEC SERVER] Error starting server: {0}", ex.Message));
            }
        }
        private void ListenForCommands()
        {
            try
            {
                executionClient = executionServer.AcceptTcpClient();
                executionStream = executionClient.GetStream();
                executionReader = new StreamReader(executionStream, Encoding.UTF8);
                connected = true;
                Print("[EXEC SERVER] Python connected! Listening for execution commands...");
                while (connected && running)
                {
                    string line = executionReader.ReadLine();
                    if (line == null)
                    {
                        Print("[EXEC SERVER] Python disconnected");
                        connected = false;
                        break;
                    }
                    Print(string.Format("[EXEC SERVER] << RECEIVED: '{0}'", line));
                    
                    // Asegurar ejecución en el hilo principal de manera robusta
                    if (ChartControl != null)
                    {
                        ChartControl.Dispatcher.InvokeAsync(() => ProcessExecutionCommand(line));
                    }
                    else if (System.Windows.Application.Current != null)
                    {
                        // Fallback si no hay ChartControl (ej. Strategy Analyzer o Headless)
                        Print("[WARNING] ChartControl is null. Using App Dispatcher.");
                        System.Windows.Application.Current.Dispatcher.InvokeAsync(() => ProcessExecutionCommand(line));
                    }
                    else
                    {
                         Print("[ERROR] No Dispatcher available to process command!");
                    }
                }
            }
            catch (Exception ex)
            {
                Print(string.Format("[EXEC SERVER] Error in listener: {0}", ex.Message));
                connected = false;
            }
        }
        private void ProcessExecutionCommand(string command)
        {
            try
            {
                // DEBUG LOG
                Print(string.Format("[DEBUG] Processing: {0}", command));
                // Format: EXECUTE;SELL_PRICE;BUY_PRICE;TIMEOUT;TP;SL;BOTH_SIDES
                string[] parts = command.Split(';');
                if (parts.Length < 7) 
                {
                    Print("[ERROR] Invalid command length.");
                    return;
                }
                if (parts[0].Trim().ToUpper() != "EXECUTE") return;
                // Parse parameters
                double sellPrice = double.Parse(parts[1], System.Globalization.CultureInfo.InvariantCulture);
                double buyPrice = double.Parse(parts[2], System.Globalization.CultureInfo.InvariantCulture);
                int timeoutMinutes = int.Parse(parts[3]);
                double tpPoints = double.Parse(parts[4], System.Globalization.CultureInfo.InvariantCulture);
                double slPoints = double.Parse(parts[5], System.Globalization.CultureInfo.InvariantCulture);
                bool bothSides = parts[6].Trim() == "1";
                DateTime expirationTime = DateTime.Now.AddMinutes(timeoutMinutes);
                string newOcoGroupId = Guid.NewGuid().ToString("N").Substring(0, 8); // ID único para este par
                Print(string.Format("[EXEC] NEW COMMAND | OCO Group: {0}", newOcoGroupId));
                Print(string.Format("[EXEC] SELL @ {0:F2} | BUY @ {1:F2}", sellPrice, buyPrice));
                
                // SIEMPRE lanzamos ambas órdenes (Techo y Suelo)
                // 1. SELL LIMIT (Techo)
                PlaceUnmanagedOrder("SELL", sellPrice, tpPoints, slPoints, expirationTime, newOcoGroupId, bothSides);
                // 2. BUY LIMIT (Suelo)
                PlaceUnmanagedOrder("BUY", buyPrice, tpPoints, slPoints, expirationTime, newOcoGroupId, bothSides);
            }
            catch (Exception ex)
            {
                Print(string.Format("[EXEC] Error processing command: {0}", ex.Message));
                Print(string.Format("[EXEC] StackTrace: {0}", ex.StackTrace));
            }
        }
        private void PlaceUnmanagedOrder(string side, double entryPrice, double tpPoints, double slPoints, DateTime expiration, string ocoGroupId, bool bothSides)
        {
            try 
            {
                orderCounter++;
                string signalName = string.Format("{0}_{1}", side, orderCounter);
                double tpPrice = 0;
                double slPrice = 0;
                OrderAction action = OrderAction.Buy;
                
                if (side == "SELL")
                {
                    action = OrderAction.SellShort;
                    tpPrice = entryPrice - tpPoints;
                    slPrice = entryPrice + slPoints;
                }
                else // BUY
                {
                    action = OrderAction.Buy;
                    tpPrice = entryPrice + tpPoints;
                    slPrice = entryPrice - slPoints;
                }
                OrderInfo orderInfo = new OrderInfo
                {
                    InternalId = orderCounter,
                    OcoGroupId = ocoGroupId,
                    Side = side,
                    EntryPrice = entryPrice,
                    TpPrice = tpPrice,
                    SlPrice = slPrice,
                    ExpirationTime = expiration,
                    IsActive = true,
                    BothSidesAllowed = bothSides
                };
                // Guardar en diccionario ANTES de enviar
                activeOrders[signalName] = orderInfo;
                Print(string.Format("[ORDER] Submitting UNMANAGED {0} Limit @ {1:F2}", side, entryPrice));
                // ENVIAR ORDEN UNMANAGED
                Order order = SubmitOrderUnmanaged(0, action, OrderType.Limit, DefaultQuantity, entryPrice, 0, "", signalName);
                
                if (order == null)
                    Print(string.Format("[ERROR] SubmitOrderUnmanaged returned NULL for {0}", signalName));
                else
                    orderInfo.EntryOrder = order;
            }
            catch (Exception ex)
            {
                 Print(string.Format("[ERROR] PlaceUnmanagedOrder failed: {0}", ex.Message));
            }
        }
        #endregion
        #region OnOrderUpdate (Gestión Manual de TP/SL y CSV)
        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice, int quantity,
            int filled, double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string nativeError)
        {
            // Buscar la orden en nuestro diccionario local usando el SignalName
            string signalName = order.Name;
            string lookupKey = signalName;
            // Ajustar key si es una orden hija (TP/SL)
            if (signalName.EndsWith("_TP"))
                lookupKey = signalName.Substring(0, signalName.Length - 3);
            else if (signalName.EndsWith("_SL"))
                lookupKey = signalName.Substring(0, signalName.Length - 3);
            
            if (!activeOrders.ContainsKey(lookupKey)) return;
            OrderInfo info = activeOrders[lookupKey];
            // Actualizar referencia si es necesario
            if (info.EntryOrder == null || info.EntryOrder != order)
            {
                if (order.OrderState != OrderState.Working && order.OrderState != OrderState.Filled)
                    // No retornamos inmediatamente para poder loggear estados como Cancelled o Rejected
                    if (order.OrderState != OrderState.Cancelled && order.OrderState != OrderState.Rejected)
                        return; 
            }
            // --- CSV LOGGING LOGIC ---
            if (info.EntryOrder != null && info.EntryOrder == order)
            {
                string eventType = "";
                string status = orderState.ToString();
                string notes = "";
                
                if (orderState == OrderState.Submitted)
                {
                    eventType = "ORDER_PLACED";
                    notes = "Entry order submitted";
                }
                else if (orderState == OrderState.Accepted)
                {
                    eventType = "ORDER_ACCEPTED";
                    notes = "Entry order accepted by broker";
                }
                else if (orderState == OrderState.Working)
                {
                    eventType = "ORDER_WORKING";
                    notes = "Entry order working";
                }
                else if (orderState == OrderState.Filled)
                {
                    eventType = "ORDER_FILLED";
                    notes = string.Format("Entry filled @ {0:F2}", averageFillPrice);
                    info.FillTime = time; // Save fill time
                }
                else if (orderState == OrderState.Cancelled)
                {
                    eventType = "ORDER_CANCELLED";
                    notes = error != ErrorCode.NoError ? string.Format("Error: {0}", error) : "Cancelled";
                }
                else if (orderState == OrderState.Rejected)
                {
                    eventType = "ORDER_REJECTED";
                    notes = string.Format("Rejected: {0}", nativeError);
                }
                
                if (!string.IsNullOrEmpty(eventType))
                {
                    WriteToCSV(
                        eventType: eventType,
                        orderId: signalName,
                        action: order.OrderAction.ToString(),
                        orderType: order.OrderType.ToString(),
                        price: limitPrice > 0 ? limitPrice : stopPrice,
                        quantity: quantity,
                        status: status,
                        notes: notes
                    );
                }
            }
            // -------------------------
            // 1. Si la orden de entrada se LLENA -> Poner TP y SL
            if (order == info.EntryOrder && orderState == OrderState.Filled)
            {
                Print(string.Format("[FILLED] {0} Order #{1} Filled @ {2:F2}", info.Side, info.InternalId, averageFillPrice));
                // Lógica OCO: Cancelar la orden hermana si no se permiten ambos lados
                if (!info.BothSidesAllowed)
                {
                    CancelSiblingOrder(info.OcoGroupId, signalName);
                }
                // Colocar TP y SL (Unmanaged)
                if (info.Side == "SELL")
                {
                    // Para cerrar Short -> Buy Limit (TP) y Buy Stop (SL)
                    info.TpOrder = SubmitOrderUnmanaged(0, OrderAction.BuyToCover, OrderType.Limit, quantity, info.TpPrice, 0, "", signalName + "_TP");
                    // CORREGIDO: OrderType.StopMarket
                    info.SlOrder = SubmitOrderUnmanaged(0, OrderAction.BuyToCover, OrderType.StopMarket, quantity, 0, info.SlPrice, "", signalName + "_SL");
                }
                else // BUY
                {
                    // Para cerrar Long -> Sell Limit (TP) y Sell Stop (SL)
                    info.TpOrder = SubmitOrderUnmanaged(0, OrderAction.Sell, OrderType.Limit, quantity, info.TpPrice, 0, "", signalName + "_TP");
                    // CORREGIDO: OrderType.StopMarket
                    info.SlOrder = SubmitOrderUnmanaged(0, OrderAction.Sell, OrderType.StopMarket, quantity, 0, info.SlPrice, "", signalName + "_SL");
                }
                
                Print(string.Format("[ATM] Placed TP @ {0:F2} | SL @ {1:F2}", info.TpPrice, info.SlPrice));
            }
            // 2. Si TP o SL se llenan -> Cancelar el otro (OCO de Salida) y Loggear Trade Closed
            if (order == info.TpOrder && orderState == OrderState.Filled)
            {
                Print("[EXIT] TP Hit! Cancelling SL...");
                if (info.SlOrder != null) CancelOrder(info.SlOrder);
                info.IsActive = false;
                // CSV Log Trade Closed (Profit)
                double duration = (time - info.FillTime).TotalSeconds;
                double pnl = CalculatePnL(info, averageFillPrice);
                
                WriteToCSV(
                    eventType: "TRADE_CLOSED",
                    orderId: signalName,
                    action: order.OrderAction.ToString(),
                    orderType: "TARGET",
                    price: averageFillPrice,
                    quantity: filled,
                    status: "FILLED",
                    pnl: pnl,
                    exitReason: "TARGET",
                    durationSec: duration,
                    notes: string.Format("TP hit @ {0:F2}", averageFillPrice)
                );
            }
            else if (order == info.SlOrder && orderState == OrderState.Filled)
            {
                Print("[EXIT] SL Hit! Cancelling TP...");
                if (info.TpOrder != null) CancelOrder(info.TpOrder);
                info.IsActive = false;
                // CSV Log Trade Closed (Loss)
                double duration = (time - info.FillTime).TotalSeconds;
                double pnl = CalculatePnL(info, averageFillPrice);
                
                WriteToCSV(
                    eventType: "TRADE_CLOSED",
                    orderId: signalName,
                    action: order.OrderAction.ToString(),
                    orderType: "STOP",
                    price: averageFillPrice,
                    quantity: filled,
                    status: "FILLED",
                    pnl: pnl,
                    exitReason: "STOP",
                    durationSec: duration,
                    notes: string.Format("SL hit @ {0:F2}", averageFillPrice)
                );
            }
        }
        private void CancelSiblingOrder(string groupId, string currentSignalName)
        {
            // Buscar otra orden con el mismo GroupID pero diferente nombre
            foreach (var kvp in activeOrders)
            {
                if (kvp.Value.OcoGroupId == groupId && kvp.Key != currentSignalName)
                {
                    if (kvp.Value.EntryOrder != null && kvp.Value.EntryOrder.OrderState == OrderState.Working)
                    {
                        Print(string.Format("[OCO] Cancelling sibling order {0}", kvp.Key));
                        CancelOrder(kvp.Value.EntryOrder);
                    }
                }
            }
        }
        #endregion
        #region OnBarUpdate (Timeouts)
        protected override void OnBarUpdate()
        {
            // Verificar Timeouts
            // Nota: En Unmanaged debemos ser cuidadosos al iterar y modificar
            
            List<string> toRemove = new List<string>();
            foreach (var kvp in activeOrders)
            {
                OrderInfo info = kvp.Value;
                // Solo verificar timeout si la orden de entrada sigue Working (no llena)
                if (info.EntryOrder != null && info.EntryOrder.OrderState == OrderState.Working)
                {
                    if (DateTime.Now > info.ExpirationTime)
                    {
                        Print(string.Format("[TIMEOUT] Cancelling expired order {0}", kvp.Key));
                        CancelOrder(info.EntryOrder);
                        toRemove.Add(kvp.Key);
                    }
                }
            }
            // Limpieza básica del diccionario (opcional, para no crecer infinito)
            foreach (string key in toRemove)
            {
                // No removemos inmediatamente para mantener logs, pero podríamos marcar como inactiva
                activeOrders[key].IsActive = false;
            }
        }
        #endregion
        #region Disconnect
        private void DisconnectAll()
        {
            running = false;
            connected = false;
            if (listenerThread != null && listenerThread.IsAlive) listenerThread.Join(1000);
            if (executionReader != null) try { executionReader.Close(); } catch { }
            if (executionClient != null) try { executionClient.Close(); } catch { }
            if (executionServer != null) try { executionServer.Stop(); } catch { }
        }
        #endregion
        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Execution Port", Order = 1, GroupName = "Connection")]
        public int ExecutionPort { get; set; }
        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Default Quantity", Order = 2, GroupName = "Parameters")]
        public int DefaultQuantity { get; set; }
        #endregion
    }
}