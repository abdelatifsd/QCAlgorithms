#region imports
from AlgorithmImports import *
#endregion
from math import ceil,floor
import datetime as dt
import pandas as pd
import numpy as np
from sklearn import linear_model
from prophet import Prophet

# Your New Python File
class MainAlgo(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2020,1,1)
        self.SetEndDate(2022,12,8)
        self.SetCash(1000000)
    
        self.ticker = "RTX"
        self.resolution = Resolution.Daily
        equity = self.AddEquity(self.ticker, self.resolution)
        equity.SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.equity_symbol = equity.Symbol
        #self.vix_symbol = self.AddEquity("VIX").Symbol

        self.Exposure = None
        self.profitPercentage = None
        self.lossPercentage = None

        # Strategy toggles
        self.lookBack = 50
        self.trendlinelookBack = 22
        self.rdv_threshold = 1
        self.strategy = "divergence" #"bullish slope consolidation" #"divergence"
        self.state = "bear" # bull, bear, or both
        self.trendline_support:bool=False
        self.trail_stop = True
        self.trailPercent = 0.6 # Adjust based on stock volatility
        self.slope_disparity = 0.2
        self.systematic_profit_caputre = {1.0:1.0}

        self.boughtAtNegativeSlope:bool=False
        self.bullish_consolidation:bool = False
        self.bullish_divergence:bool=False
        self.bearish_divergence:bool=False

        self.current_play = ""

        self.list_of_trails = []
        self.trailingPerformance = 0
        self.currentPercentPerformance = 0
        
        self.oscillator = self.RSI(self.equity_symbol, self.lookBack, MovingAverageType.Simple)
        self.rdv = self.RDV(self.equity_symbol, self.lookBack)
        self.slope = self.return_lookback_slope()
        self.oscillator_previous_values = []
        self.indicator_slope = 0
        self.trend_line_slope = 0

        self.entry_point = 0
        self.exit_point = 0

        self.bullish_divergence_point = 0
        self.bearish_divergence_point = 0
        self.bullish_consolidation_point = 0

        # use the underlying equity GOOG as the benchmark
        self.SetBenchmark(self.equity_symbol)


    def OnOrderEvent(self, orderevent):
        # check if orderevent is a fill
        if orderevent.Status == OrderStatus.Filled:
            symbol = orderevent.Symbol
            fill_price = orderevent.FillPrice
            current_price = self.Securities[symbol].Price
    
    def OnData(self, slice):
        self.entry_point = 0
        self.exit_point = 0
        self.bullish_divergence_point = 0
        self.bearish_divergence_point = 0
        self.bullish_consolidation_point = 0

        if not self.oscillator.IsReady: 
            return
        else:
            if len(self.oscillator_previous_values) < self.lookBack:
                self.oscillator_previous_values.append(self.oscillator.Current.Value)
            else:
                self.oscillator_previous_values.pop(0)
                self.oscillator_previous_values.append(self.oscillator.Current.Value)
                self.indicator_slope = self.return_stochastic_lookback_slope()
        
        if self.rdv.IsReady:
            current_rdv = self.rdv.Current.Value
        else:
            return
        try:
            self.slope = self.return_lookback_slope()
        except:
            return
        
        if not self.indicator_slope: return 

        if self.trendline_support:
            self.trend_line_slope = self.prophet_trendline_slope()

        ### CONSOLIDATION ###
        if self.strategy == "bullish slope consolidation":

            if self.indicator_slope < 0 and self.slope < 0:
                delta = abs(self.indicator_slope - self.slope)
                if delta <= 0.1:
                    self.bullish_consolidation = True
                    self.bullish_consolidation_point = 100
                else:
                    self.bullish_consolidation = False
                    self.bullish_consolidation_point = 0
            
            if self.bullish_consolidation == True:
                if current_rdv >= 2 and not self.Portfolio.Invested: # and current_rdv > 1.5
                    self.Exposure = 0.5
                    self.profitPercentage = 0.3
                    self.lossPercentage = -0.2 

                    quantity = self.CalculateOrderQuantity(self.equity_symbol, self.Exposure)

                    if self.slope < 0:
                        self.boughtAtNegativeSlope = True
                    else:
                        self.boughtAtNegativeSlope = False
                    #self.Debug(f"oscillator is at {self.oscillator.Current.Value}")
                    self.MarketOrder(self.equity_symbol, quantity)
                    self.entry_point = 200
                    self.Debug(f"Market buy order was placed")
            else:
                if current_rdv >= 2 and self.oscillator.Current.Value>80 and not self.Portfolio.Invested: # and current_rdv > 1.5
                    self.Exposure = 0.3
                    self.profitPercentage = 0.1
                    self.lossPercentage = -0.1

                    quantity = self.CalculateOrderQuantity(self.equity_symbol, self.Exposure)
                    
                    #self.Debug(f"oscillator is at {self.oscillator.Current.Value}")
                    self.MarketOrder(self.equity_symbol, quantity*-1)
                    self.entry_point = 200
                    self.Debug(f"Market sell order was placed")

        ### DIVERGENCE ###
        if self.strategy == "divergence": 

            slope_delta = self.indicator_slope - self.slope
            # Determine what kind of divergences exist if they do
            if slope_delta > self.slope_disparity: # If indicator slope is greater than the underlyings slope by X%, bullish divergence detected
                self.bullish_divergence = True
                self.bearish_divergence = False
                #self.Debug("Bullish divergence detected.")
                self.bullish_divergence_point = 100
                self.bearish_divergence_point = 0

            elif (slope_delta < -self.slope_disparity):
                self.bearish_divergence = True
                self.bullish_divergence = False
                #self.Debug("Bearish divergence detected.")
                self.bearish_divergence_point = 100
                self.bullish_divergence_point = 0
            else:
                self.bullish_divergence = False
                self.bearish_divergence = False
                self.bearish_divergence_point = 0
                self.bullish_divergence_point = 0

            if self.trendline_support:
                if self.bullish_divergence and (self.state == "both" or self.state == "bull") and self.trend_line_slope > 0:
                    if not self.Portfolio.Invested: # and current_rdv > 1
                        self.Exposure = 0.5
                        self.profitPercentage = 0.3
                        self.lossPercentage = -0.15

                        quantity = self.CalculateOrderQuantity(self.equity_symbol, self.Exposure)

                        if self.slope < 0:
                            self.boughtAtNegativeSlope = True
                        else:
                            self.boughtAtNegativeSlope = False
                        
                        self.MarketOrder(self.equity_symbol, quantity)
                        self.current_play = "bull"

                        self.entry_point = 200
                elif self.bearish_divergence and (self.state == "both" or self.state == "bear") and self.trend_line_slope < 0:
                    if not self.Portfolio.Invested: # and current_rdv > 1
                        self.Exposure = 0.5
                        self.profitPercentage = 0.3
                        self.lossPercentage = -0.15

                        quantity = self.CalculateOrderQuantity(self.equity_symbol, self.Exposure)
                        
                        self.MarketOrder(self.equity_symbol, quantity*-1)
                        self.current_play = "bear"
                        self.entry_point = 200
            else:
                if self.bullish_divergence and current_rdv > self.rdv_threshold and (self.state == "both" or self.state == "bull"):
                    if not self.Portfolio.Invested: # and current_rdv > 1
                        self.Exposure = 0.5
                        self.profitPercentage = 0.3
                        self.lossPercentage = -0.15

                        quantity = self.CalculateOrderQuantity(self.equity_symbol, self.Exposure)

                        if self.slope < 0:
                            self.boughtAtNegativeSlope = True
                        else:
                            self.boughtAtNegativeSlope = False
                        
                        self.MarketOrder(self.equity_symbol, quantity*-1)
                        self.current_play = "bear"
                        self.entry_point = -200
                elif self.bearish_divergence and current_rdv > self.rdv_threshold and (self.state == "both" or self.state == "bear"):
                    if not self.Portfolio.Invested: # and current_rdv > 1
                        self.Exposure = 0.5
                        self.profitPercentage = 0.3
                        self.lossPercentage = -0.15

                        quantity = self.CalculateOrderQuantity(self.equity_symbol, self.Exposure)
                        
                        self.MarketOrder(self.equity_symbol, quantity*1)
                        self.current_play = "bull"
                        self.entry_point = 200

        
        if self.Portfolio.Invested:
            self.currentPercentPerformance = self.Securities[self.equity_symbol].Holdings.UnrealizedProfitPercent

            """for systemicProfitThreshold, exitPercentage in self.systematic_profit_caputre.items():
                if self.currentPercentPerformance >= systemicProfitThreshold:
                    quantity = self.Portfolio[self.equity_symbol].Quantity * exitPercentage
                    if self.current_play == "bull":
                        self.MarketOrder(self.equity_symbol, quantity*-1)
                    self.exit_point = 1000
                    self.Debug(f"Trade exit using systematic threshold")"""

            if self.trail_stop:
                if self.currentPercentPerformance > self.trailingPerformance:
                    self.trailingPerformance = self.currentPercentPerformance*self.trailPercent
                    self.list_of_trails.append(self.trailingPerformance)
                    self.trailingPerformance = max(self.list_of_trails)

                if self.currentPercentPerformance <= self.trailingPerformance: # and self.currentPercentPerformance>0:
                    self.Liquidate()
                    self.exit_point = 400
                    self.list_of_trails = []
                    self.trailingPerformance = 0
                    self.currentPercentPerformance = 0
                elif self.currentPercentPerformance <= self.lossPercentage: 
                    self.Liquidate()
                    self.exit_point = -400
                    self.list_of_trails = []
                    self.trailingPerformance = 0
                    self.currentPercentPerformance = 0
            else:
                if self.currentPercentPerformance >= self.profitPercentage:
                    self.Liquidate()
                    self.exit_point = 400
                if self.currentPercentPerformance <= self.lossPercentage: #or self.oscillator.Current.Value > 80 or (self.slope < 0 and not self.boughtAtNegativeSlope):
                    self.Liquidate()
                    self.exit_point = -400


    def return_lookback_slope(self):
        history = self.History(self.equity_symbol, self.lookBack, self.resolution)
        #self.Debug(history)
        dataset = history.loc[self.equity_symbol].reset_index()[["time","close"]]
        dataset['date_ordinal'] = pd.to_datetime(dataset['time']).map(dt.datetime.toordinal)
        reg = linear_model.LinearRegression()
        reg.fit(dataset['date_ordinal'].values.reshape(-1, 1), dataset['close'].values)
        return reg.coef_

    def return_stochastic_lookback_slope(self):
        stochastic_df = pd.DataFrame(columns=["date_ordinal","indicator_val"])
        stochastic_df.date_ordinal = [i for i in range(self.lookBack)]
        stochastic_df.indicator_val = self.oscillator_previous_values
        reg = linear_model.LinearRegression()
        reg.fit(stochastic_df['date_ordinal'].values.reshape(-1, 1), stochastic_df['indicator_val'].values)
        return reg.coef_

    def prophet_trendline_slope(self, number_of_forecast_days:int=0):
        history = self.History(self.equity_symbol, self.trendlinelookBack, self.resolution)
        df = history.loc[self.equity_symbol].reset_index()[["time","close"]].rename(columns = {"time":"ds","close":"y"})
        assert list(df.columns) == ["ds", "y"], print("dataframe columns must adhere to predefined column scheme.")
        m = Prophet(changepoint_prior_scale=0.05,changepoint_range=1)
        m.fit(df)
        future = m.make_future_dataframe(periods=number_of_forecast_days)
        forecast = m.predict(future)

        slope_df = pd.DataFrame(columns=["date_ordinal","trend_value"])
        slope_df.date_ordinal = [i for i in range(self.trendlinelookBack)]
      
        slope_df.trend_value = forecast.trend
        reg = linear_model.LinearRegression()
        reg.fit(slope_df['date_ordinal'].values.reshape(-1, 1), slope_df['trend_value'].values)
        return reg.coef_[0]  

    def OnEndOfDay(self):
        self.Plot("Indicators","oscillator", self.oscillator.Current.Value)
        self.Plot("Indicators","underlying slope", self.slope)
        self.Plot("Indicators","oscillator slope", self.indicator_slope)
        self.Plot("Indicators","trend line slope", self.trend_line_slope)
        self.Plot("Indicators","relative volume", self.rdv.Current.Value)
        
        self.Plot("Entry/Exit", "entry points", self.entry_point)
        self.Plot("Entry/Exit", "exit points", self.exit_point)

        self.Plot("Divergence","bullish divergence",self.bullish_divergence_point)
        self.Plot("Divergence","bear divergence",self.bearish_divergence_point)
        #self.Plot("Consolidation","bullish consolidation",self.bullish_consolidation_point)

        self.Plot("Performance","current performance",self.currentPercentPerformance)
        self.Plot("Performance","trailing performance",self.trailingPerformance)

        self.entry_point = 0
        self.exit_point = 0
        self.bullish_divergence_point = 0
        self.bearish_divergence_point = 0
