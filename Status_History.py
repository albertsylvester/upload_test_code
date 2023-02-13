import streamlit as st
import pandas as pd
import numpy as np
import time
import datetime
import json
import matplotlib.pyplot as plt

st.write('# Field Device Condition Monitoring')
st.caption('Last updated: xx/xx/xx 00:00:00')

if "date_input_is_disabled" not in st.session_state:
	st.session_state.date_input_is_disabled = True

def load_data():
	# Opening JSON file
	f = open('../sample.json')

	# returns JSON object as a dictionary
	data = json.load(f)
	return data

def from_json_to_dataframe(data):
    ###1. extract na
    df_all = pd.json_normalize(data).explode('status_history')
    df_status_history_na = df_all[df_all['status_history'].isna()].copy()
    df_status_history_na['id'] = df_status_history_na['id.$oid']
    df_status_history_na.drop(['id.$oid', 'status_history'], axis=1, inplace=True)
    
    ###2. extract exploded status_history
    exploded_status_history = pd.json_normalize(
        data, record_path=['status_history'], 
        meta=['tag', 'device_model', 'serial_number', 'revision', 'device_installed', 'digester', 'id'])\
                .explode('device_parameters')
    exploded_status_history['id'] = pd.json_normalize(exploded_status_history['id'])
    
    ###3.merge df
    df_final = df_status_history_na.merge(exploded_status_history, how='outer')

    ###4. rename columns
    df_final.rename(columns={'date': 'st_date', 
                             'status': 'st_status', 
                             'device_parameters': 'st_device_parameters'}, inplace=True)
    
    ###5. reordering columns
    #reordering columns
    target_feature_name = 'id'
    df_final = df_final.reindex(columns=([target_feature_name] + list([a for a in df_final.columns if a != target_feature_name])))
    
    return df_final

def plot_device_stats_barh(df_final):
	#1. Create the dataframe by grouping the digester
	all_row = list()
	for digester_name in df_final['digester'].unique():
		a_row = list()
		a_row.append(digester_name)
		for stat_now in df_final['st_status'].unique():
		    a_row.append(len(df_final[((df_final['digester']==digester_name) & (df_final['st_status']==stat_now))]))
		all_row.append(a_row)

	stats_summary = pd.DataFrame(data=all_row, columns=['digester', 'OK', 'Alarm', 'Warning'])
	stats_summary.set_index('digester', inplace=True)

	#2. set up color pallete and plot
	color_pallete ={'red': '#f44336', 'yellow': '#fbc02d', 'green': '#4caf50'}

	fig, ax = plt.subplots()
	stats_summary.plot(kind='barh', 
						ax=ax, 
						ylabel='DIGESTER', 
						# xlabel='#Count',
                        color={'OK':color_pallete['green'], 
                               'Alarm':color_pallete['red'], 
                               'Warning':color_pallete['yellow']}, 
                        title='Device Statistics')

	#3. Draw labels
	for index, row in enumerate(all_row):
	    bar_values = row[1:]
	    for index_bar, bar_value in enumerate(bar_values):
	        if index_bar == 0:
	            c = color_pallete['green']
	        elif index_bar == 1:
	            c = color_pallete['red']
	        else:
	            c = color_pallete['yellow']
	        ax.text(bar_value+0.1, 
	        	index+(index_bar-1.15)*0.2, 
	        	bar_value, 
	        	ha='center',
	        	c=c)

	st.pyplot(fig)

def get_list_of_digesters(df_final):
	return ['All'] + df_final['digester'].unique().tolist()

def generate_custom_dataframe_table(df_final):
	def generate_time_(time_data, time_type):
		return str(time_data.year)+'-'+str(time_data.month)+'-'+str(time_data.day) +(' 00:00:00' if time_type == 'begin' else ' 23:59:59')

	##choose selected columns and user choice
	custom_columns = ['tag', 'device_model', 'digester', 'st_date', 'st_status', 'st_device_parameters']
	digester_query = st.session_state.id_digester_list_select_box
	
	##process time frame
	show_last = st.session_state.id_show_last_select_box.lower()	
	if show_last == 'custom':
		start_date = st.session_state.id_start_date
		end_date = st.session_state.id_end_date
	else:#not custom
		end_date = datetime.date.today()
		if show_last == 'week':
		    start_date = end_date - datetime.timedelta(days=7)
		elif show_last == 'month':
		    start_date = end_date - datetime.timedelta(days=30)
		elif show_last == 'year':
		    start_date = end_date - datetime.timedelta(days=365*3)
		else: #24 hours
		    start_date = end_date - datetime.timedelta(hours=24)

	start_date_with_time = generate_time_(start_date, 'begin')
	end_date_with_time = generate_time_(end_date, 'end')
	st.write('> Debug. Start time:',start_date_with_time, ' , End Time: ', end_date_with_time, ', Digester:',digester_query)

	##process digester selection
	df_final_temp = df_final[custom_columns].copy()
	# if digester_query != 'All':
	# 	df_final_temp = df_final_temp.query("digester == '{}'".format(digester_query))

	if digester_query == 'All':#choosing all digesters
		df_final_temp = df_final_temp.query("st_date >= '{}' & st_date < '{}'".format(start_date_with_time, end_date_with_time))
	else:#selecting a digester
		df_final_temp = df_final_temp.query("digester == '{}' & st_date >= '{}' & st_date < '{}'".format(digester_query, start_date_with_time, end_date_with_time))

	##display the result
	st.table(df_final_temp)

def show_last_select_box_has_changed():
	#to activate the date_input with regards to show_last select box
	if st.session_state.id_show_last_select_box == 'Custom':
		st.session_state.date_input_is_disabled = False
	else:
		st.session_state.date_input_is_disabled = True

###DATA PREPARATION###
#fetch data from DB
data = load_data()

#convert and flatten json to dataframe
df_final = from_json_to_dataframe(data)

#convert to datetime
df_final['st_date'] = pd.to_datetime(df_final['st_date'], format='%d/%m/%Y %H.%M.%S')

#fill NaN st_status with OK value
df_final['st_status'] =  df_final['st_status'].fillna('OK')


###UI###
# st.write(df_final)
#make columns
col_a1, col_a2, col_a3 = st.columns(3)
with col_a1:
	show_last_select_box = st.selectbox(label='Show Last', 
		options=['24 Hours', 'Week', 'Month', 'Year', 'Custom'], 
		key='id_show_last_select_box',
		on_change=show_last_select_box_has_changed)

with col_a2:
	start_date = st.date_input(
		label="Custom Start Date", 
		# value=datetime.date(2023, 2, 14),
		value=datetime.datetime.now(),
		key='id_start_date',
		disabled=st.session_state.date_input_is_disabled,
		)

with col_a3:
	end_date = st.date_input(
		label="Custom End Date", 
		value=datetime.datetime.now(),
		key='id_end_date',
		disabled=st.session_state.date_input_is_disabled,
		)

# add margin / space
st.write('')

#plot bar chart
plot_device_stats_barh(df_final)

#draw select box for digester
#all keys are in session_state
digester_list_select_box = st.selectbox(
	label='Choose Digester', 
	options=get_list_of_digesters(df_final), 
	key='id_digester_list_select_box', 
	# on_change=digester_select_box_has_changed,
	# args=(df_final,)
	)


#Display the dataframe
st.write('> Debug. Show Last:', st.session_state.id_show_last_select_box)
generate_custom_dataframe_table(df_final)



















