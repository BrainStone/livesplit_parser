import xml.etree.ElementTree as ET
import xmltodict
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta

class LivesplitData:
    def __init__(self, fpath, time_key='RealTime'):
        if time_key not in ['RealTime', 'GameTime']:
            raise ValueError('Time must be either RealTime or GameTime')

        tree = ET.parse(fpath)
        xml_data = tree.getroot()
        xml_str = ET.tostring(xml_data, encoding='utf-8', method='xml')
        xml_dict = dict(xmltodict.parse(xml_str))['Run']
        self.time_key = time_key
        self.name = fpath[:-4]
        self.num_attempts = int(xml_dict['AttemptCount'])
        self.num_completed_attempts = self.__compute_finished_runs_count(xml_dict)
        self.percent_runs_completed = self.num_completed_attempts / self.num_attempts * 100
        self.attempt_info_df = self.__parse_attempt_data(xml_dict)
        self.attempt_info_df = self.__add_float_seconds_cols(self.attempt_info_df, [val for val in list(self.attempt_info_df.columns) if val not in ['started', 'isStartedSynced', 'ended', 'isEndedSynced', 'RunCompleted']])
        self.split_info_df = self.__parse_segment_data(xml_dict, self.attempt_info_df)
        self.split_info_df = self.__add_float_seconds_cols(self.split_info_df, ['PersonalBest', 'BestSegment', 'Average', 'Median'])

        # Optional metadata
        platform = xml_dict.get('Metadata', {}).get('Platform', {})
        
        self.game_name = xml_dict.get('GameName')
        self.game_icon = xml_dict.get('GameIcon')
        self.category_name = xml_dict.get('CategoryName')
        self.layout_path = xml_dict.get('LayoutPath')
        self.platform_name = platform.get('#text')
        self.platform_uses_emulator = {'False': False, 'True': True}.get(platform.get('@usesEmulator'))
        self.offset = xml_dict.get('Offset')
        self.version = xml_dict.get('@version')

    def export_data(self):
        # Specify the Excel file path
        excel_file_path = f'{self.name}.xlsx'
        df1 = self.attempt_info_df[[v for v in self.attempt_info_df.columns if not '_Sec' in v]]
        df2 = self.split_info_df[['PersonalBest', 'PersonalBestSplitTime', 'BestSegment', 'BestSegmentSplitTime', 'StDev', 'Average', 'AverageSplitTime', 'Median', 'MedianSplitTime', 'NumRunsPassed', 'PercentRunsPassed']]

        # Create a Pandas Excel writer using ExcelWriter
        with pd.ExcelWriter(excel_file_path, engine='xlsxwriter') as writer:
            # Write each dataframe to a different sheet
            df1.to_excel(writer, sheet_name='Attempt Info')
            df2.to_excel(writer, sheet_name='Splits Info')

    def plot_num_resets(self, drop_na=False, time_limit=None, plot=True) :
        #retain only ids and times
        df = self.__get_completed_runs_data()[[self.time_key]]

        #sets max time param and drops runs w skipped splits
        time = 9999999
        if time_limit != None :
            time = self.__convert_timestr_to_float(time_limit)
        if drop_na:
            df.dropna(inplace=True)
        arr = df.index

        #create arrays of times to graph
        lis1 = []
        lis2 = []
        last = 0
        for i in arr:
            if self.__convert_timestr_to_float(df[self.time_key][i]) < time :
                lis2.append(i)
                lis1.append(i-last-1)
                last = i

        #plot info
        sns.lineplot(x=lis2, y=lis1, marker='o', linestyle='-')

        plt.xlim(0, 1.05 * self.num_attempts)
        plt.ylim(0, 1.1 * max(lis1))
        plt.title('Times reset between completed runs')
        plt.xlabel('Attempt #')
        plt.ylabel('Resets Prior to Run Completion')
        plt.xticks(rotation=90)
        if plot:
            plt.show()

    def chance_run_continues(self, split_name):
        df = self.split_info_df[['NumRunsPassed']]
        
        #set curr to the # of attempts making it past the previous split
        curr = self.num_attempts
        for i in df.index:
            if i == split_name:
                previous = curr
            curr = df['NumRunsPassed'][i]
        # %of runs (which made it to this split) that made it past this split
        return df['NumRunsPassed'][split_name] / previous * 100
    
    def percent_runs_past(self, split_name) :
        # %of runs that made it past this split
        return self.split_info_df['NumRunsPassed'][split_name] / self.num_attempts * 100
    
    def plot_completed_over_time(self, only_pbs=False, drop_na=False, time_limit=None, plot=True) :
        #set ids from 0, remove useless columns
        df = self.__get_completed_runs_data()[['ended', self.time_key]].reset_index(drop= True)
        
        #max time info and drops run with skipped splits
        time =9999999
        if time_limit != None:
            time = self.__convert_timestr_to_float(time_limit)/60
        if drop_na:
            df.dropna(inplace=True)

        lis = []
        lis2 = []

        #determine first finished run (for only pbs)
        lowest = self.__convert_timestr_to_float(df[self.time_key][0])
        
        #create arrays of times to graph
        if only_pbs: #add only pbs
            for i in range(self.num_completed_attempts):
                #check if current run was a pb or not, add to graph if so
                curr = self.__convert_timestr_to_float(df[self.time_key][i])/60
                if curr < lowest and curr < time:
                    lis.append(curr)
                    lis2.append(df['ended'][i])
                    lowest = curr
                
        else : #add all completed runs
            for i in range(self.num_completed_attempts):
                curr = self.__convert_timestr_to_float(df[self.time_key][i])/60
                if curr < time :
                    lis.append(self.__convert_timestr_to_float(df[self.time_key][i]) / 60)
                    lis2.append(df['ended'][i])
        
        #plot info
        sns.lineplot(y= lis, x= lis2, marker='o', linestyle='-')
        
        plt.title('Completed Runs Over Time')
        plt.xlabel('Date')
        plt.ylabel('Run Times (m)')
        plt.xticks(rotation=90)
        if plot:
            plt.show()


    def plot_splits_violin_plot(self, completed_runs=False, drop_na=True, plot=True):
        data = self.attempt_info_df[[c for c in self.attempt_info_df.columns if '_Sec' in c and c not in ['RealTime_Sec', 'GameTime_Sec']]]
        if completed_runs:
            data = self.__get_completed_runs_data()[[c for c in data.columns if '_Sec' in c and c not in ['RealTime_Sec', 'GameTime_Sec']]]
        data.rename(columns={c:c[:-4] for c in data.columns}, inplace=True)
        if drop_na:
            data.dropna(inplace=True)
        data = pd.melt(data, var_name='Split Name', value_name='Split Length (Sec)')
        sns.violinplot(x='Split Name', y='Split Length (Sec)', data=data)
        plt.xticks(rotation=90)
        plt.title('Split Time Distributions')
        if plot:
            plt.show()

    def plot_completed_runs_lineplot(self, drop_na=True, scale='seconds', plot=True):
        data = self.__get_completed_runs_data()
        plot_cols = [c for c in data.columns if '_Sec' in c and c not in ['RealTime_Sec', 'GameTime_Sec']]
        data = data[plot_cols]
        data.rename(columns = {c:c[:-4] for c in data.columns}, inplace=True)

        if drop_na:
            data.dropna(inplace=True)

        for c in data.columns:
            if drop_na:
                avg = data[c].mean()
            else:
                avg = self.__convert_timestr_to_float(self.split_info_df['Average'][c])
            if scale == 'minutes':
                avg /= 60

            for i in data.index:
                if not pd.isna(data[c][i]):
                    if scale == 'seconds':
                        data.loc[i, c] = data[c][i] - avg
                    elif scale == 'minutes':
                        data.loc[i, c] = (data[c][i]/60) - avg

        fig, ax = plt.subplots()
        for index, row in data.iterrows():
            if int(index) != self.__get_pb_id():
                ax.plot(row.index, row.values, color='grey')
            
        if self.__get_pb_id() in data.index:
            ax.plot(row.index, row.values, color='red', label='Personal Best')
        plt.xlabel('Split Name')
        plt.xticks(rotation=90)
        plt.ylabel('Deviation From Mean (Seconds)')
        plt.title('Run Time Distributions')
        plt.legend()
        if plot:
            plt.show()

    def plot_completed_runs_heatmap(self, drop_na=True, plot=True):
        data = self.__get_completed_runs_data()
        plot_cols = [c for c in data.columns if '_Sec' in c and c not in ['RealTime_Sec', 'GameTime_Sec']]
        data = data[plot_cols]
        data.rename(columns={c:c[:-4] for c in data.columns}, inplace=True)
        
        if drop_na:
            data.dropna(inplace=True)

        for c in data.columns:
            if drop_na:
                avg = data[c].mean()
            else:
                avg = self.__convert_timestr_to_float(self.split_info_df['Average'][c])

            for i in data.index:
                if not pd.isna(data[c][i]):        
                    data.loc[i, c] = data[c][i] - avg

        hm = sns.heatmap(data=data, linewidths=0.5, linecolor='black')

        plt.title('Heatmap of Completed Run Splits (Compared to Avg)')
        plt.xlabel('Split Name')
        plt.xticks(rotation=90)
        plt.ylabel('Completed Run ID')
        if plot:
            plt.show()
    
    ##################### CLASS HELPER FUNCTIONS ##############
    def __compute_finished_runs_count(self, data):
        finished_count = 0

        for d in data['AttemptHistory']['Attempt']:
            if self.time_key in d:
                finished_count += 1
        
        return finished_count

    def __parse_attempt_data(self, data):
        # initial data parsing
        attempt_info_df = pd.DataFrame(data['AttemptHistory']['Attempt'])
        has_game_time = 'GameTime' in attempt_info_df
        extract_columns = ['id', 'started', 'isStartedSynced', 'ended', 'isEndedSynced', 'RealTime']
        result_columns = ['started', 'isStartedSynced', 'ended', 'isEndedSynced', 'RunCompleted', 'RealTime']

        if not has_game_time and self.time_key == 'GameTime':
            raise ValueError("time_key is \"GameTime\", but the splits don't have that column")

        if 'PauseTime' in attempt_info_df:
            attempt_info_df.drop(columns=['PauseTime'], inplace=True)
        if has_game_time:
            extract_columns.append('GameTime')
            result_columns.append('GameTime')
        attempt_info_df.columns = extract_columns
        attempt_info_df['id'] = attempt_info_df['id'].astype(int)
        attempt_info_df['isStartedSynced'] = attempt_info_df['isStartedSynced'].astype(bool)
        attempt_info_df['isEndedSynced'] = attempt_info_df['isEndedSynced'].astype(bool)
        attempt_info_df['started'] = pd.to_datetime(attempt_info_df['started'], format='%m/%d/%Y %H:%M:%S')
        attempt_info_df['ended'] = pd.to_datetime(attempt_info_df['ended'], format='%m/%d/%Y %H:%M:%S')
        if has_game_time:
            attempt_info_df['GameTime'] = attempt_info_df['GameTime'].astype(str)
        attempt_info_df.set_index('id', inplace=True)

        # compute time attempt lasted for
        run_finished = []

        for i in attempt_info_df.index:
            if pd.isna(attempt_info_df['RealTime'][i]):
                run_finished.append(False)
                attempt_info_df.loc[i, 'RealTime'] = attempt_info_df['ended'][i] - attempt_info_df['started'][i]
            else:
                run_finished.append(True)
        attempt_info_df['RunCompleted'] = run_finished
        attempt_info_df['RunCompleted'] = attempt_info_df['RunCompleted'].astype(bool)
        attempt_info_df['RealTime'] = pd.to_timedelta(attempt_info_df['RealTime'])
        attempt_info_df['RealTime'] = attempt_info_df['RealTime'].astype(str).apply(lambda x: str(x).split()[-1])
        # attempt_info_df['RealTime'] = pd.to_timedelta(attempt_info_df['RealTime'])
        attempt_info_df = attempt_info_df[result_columns]

        # pull segment history data
        # start by getting the index values (from the attempt_history_df)
        idx = list(attempt_info_df.index)

        # next, get the column values
        col_names = []

        for d in data['Segments']['Segment']:
            col_names.append(d['Name'])

        # now create an empty DataFrame
        segment_history_df = pd.DataFrame(index=idx, columns=col_names)

        for d in data['Segments']['Segment']:
            seg_name = d['Name']

            if not d['SegmentHistory']:
                continue

            for t in d['SegmentHistory']['Time']:
                # print(t)
                try:
                    segment_history_df.loc[int(t['@id']), seg_name] = t[self.time_key]
                except:
                    pass

        segment_history_df = segment_history_df.sort_index()
        segment_history_df = segment_history_df[segment_history_df.index > 0]

        # merge segment history into attempt history dataframe
        attempt_info_df = pd.merge(attempt_info_df, segment_history_df, left_index = True, right_index=True, how='outer')

        return attempt_info_df

    def __parse_segment_data(self, data, attempt_info_df):
        # initial data pull
        segment_info_df = pd.DataFrame(data['Segments']['Segment'])
        segment_info_df.set_index('Name', inplace=True)
        segment_info_df.drop('Icon', axis=1, inplace=True)

        # pop out personal best column
        pb = []

        for i in segment_info_df.index:
            if self.time_key in segment_info_df['SplitTimes'][i]['SplitTime']:
                pb.append(segment_info_df['SplitTimes'][i]['SplitTime'][self.time_key])
            else:
                pb.append(np.nan)

        segment_info_df['PersonalBest'] = pb

        # pop out best segments column
        best_seg = []

        for i in segment_info_df.index:
            if segment_info_df['BestSegmentTime'][i]:
                best_seg.append(segment_info_df['BestSegmentTime'][i][self.time_key])
            else:
                best_seg.append(np.nan)

        segment_info_df['BestSegment'] = best_seg

        # compute total number of attempts that completed said split
        split_count = []
        split_percentage = []

        for i in segment_info_df.index:
            split_count.append(attempt_info_df[i].count())
            split_percentage.append(attempt_info_df[i].count() / self.num_attempts * 100)

        segment_info_df['NumRunsPassed'] = split_count
        segment_info_df['PercentRunsPassed'] = split_percentage

        # compute standard deviation for splits
        std_splits = []

        for i in segment_info_df.index:
            std_splits.append(pd.to_timedelta(attempt_info_df[i]).std())

        segment_info_df['StDev'] = std_splits
        segment_info_df['StDev'] = segment_info_df['StDev'].astype(str).apply(lambda x: str(x).split()[-1])

        # compute average splits
        avg_splits = []

        for i in segment_info_df.index:
            avg_splits.append(pd.to_timedelta(attempt_info_df[i]).mean())

        segment_info_df['Average'] = avg_splits
        segment_info_df['Average'] = segment_info_df['Average'].astype(str).apply(lambda x: str(x).split()[-1])

        # compute median splits
        med_splits = []

        for i in segment_info_df.index:
            med_splits.append(pd.to_timedelta(attempt_info_df[i]).median())

        segment_info_df['Median'] = med_splits
        segment_info_df['Median'] = segment_info_df['Median'].astype(str).apply(lambda x: str(x).split()[-1])

        # compute columns with actual split times
        def round_time(string):
            digit = int(string[string.find('.')+5])

            if digit >= 5:
                return string[:string.find('.')+5] + str(digit+1)
            else:
                return string[:string.find('.')+6]
            
        cols = ['PersonalBest', 'BestSegment', 'Average', 'Median']

        for i in segment_info_df.index:
            for c in cols:
                if not pd.isna(segment_info_df[c][i]):
                    segment_info_df.loc[i, c] = round_time(segment_info_df[c][i])

        def compute_split_times(df, col_name):
            idx = list(df.index)
            segment_times = []
            time_format = '%H:%M:%S.%f'

            first_time = df[col_name][idx[0]]
            segment_times.append(first_time)
            sum_time = datetime.strptime(first_time, time_format)

            for i in range(1, len(idx)):
                curr_time = datetime.strptime(df[col_name][idx[i]], time_format)
                sum_time += timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=curr_time.second, microseconds=curr_time.microsecond)
                segment_times.append(sum_time.strftime(time_format))
            
            df[col_name+'SplitTime'] = segment_times

            return df

        def compute_pb_segments(df):
            idx = list(df.index)
            segment_times = []
            time_format = '%H:%M:%S.%f'

            first_time = df['PersonalBest'][idx[0]]
            segment_times.append(first_time)

            for i in range(1, len(idx)):
                curr_split_time = df['PersonalBest'][idx[i]]
                
                if pd.isna(curr_split_time):
                    segment_times.append(curr_split_time)
                
                else:
                    curr_split_time = datetime.strptime(curr_split_time, time_format)
                    for j in segment_times:
                        if not pd.isna(j):
                            temp = datetime.strptime(j, time_format)
                            curr_split_time -= timedelta(hours=temp.hour, minutes=temp.minute, seconds=temp.second, microseconds=temp.microsecond)

                    segment_times.append(curr_split_time.strftime(time_format))

            df['PersonalBestSplitTime'] = segment_times

            return df

        segment_info_df = compute_pb_segments(segment_info_df)
        segment_info_df = compute_split_times(segment_info_df, 'BestSegment')
        segment_info_df = compute_split_times(segment_info_df, 'Average')
        segment_info_df = compute_split_times(segment_info_df, 'Median')

        # clean final dataframe
        segment_info_df.drop(['SplitTimes', 'BestSegmentTime', 'SegmentHistory'], axis=1, inplace=True)
        segment_info_df.rename(columns={'PersonalBest':'PersonalBestSplitTime', 'PersonalBestSplitTime':'PersonalBest'}, inplace=True)
        segment_info_df = self.__add_float_seconds_cols(segment_info_df, ['PersonalBest', 'BestSegment', 'StDev', 'Average', 'Median'])
        segment_info_df = segment_info_df[['PersonalBest', 'PersonalBest_Sec', 'PersonalBestSplitTime', 'BestSegment', 'BestSegment_Sec', 'BestSegmentSplitTime', 'StDev', 'StDev_Sec', 'Average', 'Average_Sec', 'AverageSplitTime', 'Median', 'Median_Sec', 'MedianSplitTime', 'NumRunsPassed', 'PercentRunsPassed']]

        return segment_info_df
        
    def __convert_timestr_to_float(self, time_str):
        if time_str == 'nan':
            return float('nan')

        # Split the time string into hours, minutes, seconds, and milliseconds
        hours, minutes, seconds = map(float, time_str.split(':'))

        # Calculate the total number of seconds
        total_seconds = hours * 3600 + minutes * 60 + seconds

        return total_seconds

    def __add_float_seconds_cols(self, df, col_names):
        for c in col_names:
            vals = []

            for i in df.index:
                if pd.isna(df[c][i]):
                    vals.append(np.nan)
                else:
                    vals.append(self.__convert_timestr_to_float(df[c][i]))

            df[c+'_Sec'] = vals
            df[c+'_Sec'] = df[c+'_Sec'].astype(float)

        return df

    def __get_completed_run_ids(self):
        return self.attempt_info_df[self.attempt_info_df['RunCompleted']].index
    
    def __get_completed_runs_data(self):
        return self.attempt_info_df[self.attempt_info_df['RunCompleted']]

    def __get_pb_id(self):
        return int(self.__get_completed_runs_data()[self.time_key].idxmin())
