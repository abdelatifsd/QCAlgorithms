#region imports
from AlgorithmImports import *
#endregion
from math import ceil,floor
import datetime as dt
import pandas as pd
import numpy as np
from sklearn import linear_model


# Your New Python File
class MainAlgo(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2015,1,1)
        self.SetEndDate(2022,11,24)
        self.SetCash(100000)
        self.Exposure = None
        self.profitPercentage = None
        self.lossPercentage = None
        self.lookBack = 50
        self.boughtAtNegativeSlope:bool=False

        self.bullish_consolidation:bool = False
        self.bullish_divergence:bool=False
        self.bearish_divergence:bool=False

        self.strategy = "bullish slope consolidation"

        self.ticker = "AAPL"
        equity = self.AddEquity(self.ticker, Resolution.Daily)
        equity.SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.equity_symbol = equity.Symbol
        #self.vix_symbol = self.AddEquity("VIX").Symbol

        self.slope = self.return_lookback_slope()

        self.oscillator = self.RSI(self.equity_symbol, 14, MovingAverageType.Simple)
        self.oscillator_previous_values = []

        self.rdv = self.RDV(self.equity_symbol, 14)

        self.adx = self.ADX(self.equity_symbol, 14)
        self.negative_trend:bool=False 
        self.adx_previous_values = []

        self.adx_indicator_slope = 0
        self.indicator_slope = 0

        self.entry_point = 0
        self.exit_point = 0
        self.bear_mark = 0

        self.bullish_divergence_point = 0
        self.bullish_consolidation_point = 0

        self.currently_short:bool=False

        # use the underlying equity GOOG as the benchmark
        self.SetBenchmark(self.equity_symbol)
    
    def OnData(self, slice):
        self.entry_point = 0
        self.exit_point = 0
        self.bear_mark = 0
        self.bullish_divergence_point = 0
        self.bullish_consolidation_point = 0

        if not self.adx.IsReady: 
            return
        else:
            if len(self.adx_previous_values) < self.lookBack:
                self.adx_previous_values.append(self.adx.Current.Value)
            else:
                self.adx_previous_values.pop(0)
                self.adx_previous_values.append(self.adx.Current.Value)
                self.adx_indicator_slope = self.return_adx_lookback_slope()

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
        if not self.adx_indicator_slope: return

        "If underlying slope is still positive, but the ADX indicator is starting slope downwards and is weakning, reversal is bound."
        if self.slope > 0 and self.adx_indicator_slope < 0 and self.adx.Current.Value < 25:
            self.negative_trend = True
            self.bear_mark = 100
        else:
            self.negative_trend=False
            self.bear_mark = 0


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
                if current_rdv >= 2 and not self.Portfolio.Invested and self.negative_trend == False: # and current_rdv > 1.5
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
                elif current_rdv >= 2 and self.oscillator.Current.Value>80 and (self.negative_trend == True)  \
                                                                           and not self.Portfolio.Invested: # and current_rdv > 1.5
                    self.Exposure = 0.3
                    self.profitPercentage = 0.2
                    self.lossPercentage = -0.1

                    quantity = self.CalculateOrderQuantity(self.equity_symbol, self.Exposure)
                    
                    #self.Debug(f"oscillator is at {self.oscillator.Current.Value}")
                    self.MarketOrder(self.equity_symbol, quantity*-1)
                    self.currently_short=True
                    self.entry_point = 200
                    self.Debug(f"Market sell order was placed")


        """if self.strategy == "divergence": 
            slope_delta = self.indicator_slope - self.slope
            if slope_delta > 0.2: # If indicator slope is greater than the underlyings slope by 20%, divergence detected
                self.bullish_divergence = True
                self.Debug("Bullish divergence detected.")
                self.bullish_divergence_point = 100
            else:
                self.bullish_divergence = False
                self.bullish_divergence_point = 0

            
            if self.bullish_divergence:
                if current_rdv >= 1 and not self.Portfolio.Invested: # and current_rdv > 1.5
                    self.Exposure = 0.5
                    self.profitPercentage = 0.3
                    self.lossPercentage = -0.3  

                    quantity = self.CalculateOrderQuantity(self.equity_symbol, self.Exposure)

                    if self.slope < 0:
                        self.boughtAtNegativeSlope = True
                    else:
                        self.boughtAtNegativeSlope = False
                    #self.Debug(f"oscillator is at {self.oscillator.Current.Value}")
                    self.MarketOrder(self.equity_symbol, quantity)
                    self.entry_point = 200
                    self.Debug(f"Market order was placed")"""
                    
        
            
        if self.Portfolio.Invested:
            
            currentPercentPerformance = self.Securities[self.equity_symbol].Holdings.UnrealizedProfitPercent

            if currentPercentPerformance >= self.profitPercentage:
                self.Liquidate()
                self.exit_point = 200
                self.currently_short=False
                self.Debug(f"Trade exit with gain")
            elif currentPercentPerformance <= self.lossPercentage or (self.currently_short == True \
                                                                      and self.oscillator.Current.Value<30 \
                                                                      and self.negative_trend==False):
                self.Liquidate()
                self.exit_point = -200
                self.currently_short=False
                self.Debug(f"Trade exit with loss")

    def return_lookback_slope(self):
        history = self.History(self.equity_symbol, self.lookBack, Resolution.Daily)
        #self.Debug(history)
        dataset = history.loc[self.equity_symbol].reset_index()[["time","close"]]
        dataset['date_ordinal'] = pd.to_datetime(dataset['time']).map(dt.datetime.toordinal)
        reg = linear_model.LinearRegression()
        reg.fit(dataset['date_ordinal'].values.reshape(-1, 1), dataset['close'].values)
        return reg.coef_

    def return_stochastic_lookback_slope(self):
        stochastic_df = pd.DataFrame(columns=["date_ordinal","indicator_val"])
        stochastic_df.date_ordinal = [i for i in range(self.lookBack)]
        self.Debug(len(stochastic_df.date_ordinal))
        self.Debug(len(self.oscillator_previous_values))
        stochastic_df.indicator_val = self.oscillator_previous_values
        reg = linear_model.LinearRegression()
        reg.fit(stochastic_df['date_ordinal'].values.reshape(-1, 1), stochastic_df['indicator_val'].values)
        return reg.coef_

    def return_adx_lookback_slope(self):
        stochastic_df = pd.DataFrame(columns=["date_ordinal","indicator_val"])
        stochastic_df.date_ordinal = [i for i in range(self.lookBack)]
        self.Debug(len(stochastic_df.date_ordinal))
        self.Debug(len(self.adx_previous_values))
        stochastic_df.indicator_val = self.adx_previous_values
        reg = linear_model.LinearRegression()
        reg.fit(stochastic_df['date_ordinal'].values.reshape(-1, 1), stochastic_df['indicator_val'].values)
        return reg.coef_
                        
                
    def OnEndOfDay(self):
        self.Plot("Indicators","oscillator", self.oscillator.Current.Value)
        self.Plot("Indicators","underlying slope", self.slope)
        self.Plot("Indicators","oscillator slope", self.indicator_slope)
        self.Plot("Indicators","relative volume", self.rdv.Current.Value)
        self.Plot("Indicators","adx", self.adx.Current.Value)
        self.Plot("Indicators","adx slope",self.adx_indicator_slope)
        
        self.Plot("Entry/Exit", "entry points", self.entry_point)
        self.Plot("Entry/Exit", "exit points", self.exit_point)

        self.Plot("Divergence","bullish divergence",self.bullish_divergence_point)
        self.Plot("Consolidation","bullish consolidation",self.bullish_consolidation_point)

        self.Plot("Bear mark","bear mark",self.bear_mark)
