import string
import datetime

# required fields:
def dataget(name: string):
    print("Get param:" + name)
    #return data.get(name)
    

def callService(serviceName: string, action: string, service_data):
    loginfo("Calling " + serviceName + "." + action + ":" + str(service_data))
    try:
        service.call(serviceName, action, **service_data)
    except Exception as e:
        log.error(e) 

def stateget(name: string):
    try:    
        result=str(state.get(name))
    
        #loginfo("stateget: " + name+"="+result)
        return result
    except Exception as e:
        log.error("Error in state.get(" + str(name) + ") " + str(e)) 
    
    return None
    
def loginfo(values: string):
    log.info(values)
    print(values)

"""
ioanas_smart_heater_entity_id: climate.zhimi_heater_mc2_54_48_e6_89_5f_4f
input_number.min_ioanas_bedroom_temperature
fabian_min_temp_entity_id: input_number.min_fabians_bedroom_temperature
dining_min_temp_entity_id: input_number.min_dining_temperature
smallbedroom_min_temp_entity_id: input_number.min_small_bedroom_temperature
input_boolean.ioana_sleeps_in_her_room
"""

m_ioanas_smart_heater_entity_id = dataget("ioanas_smart_heater_entity_id")#climate.zhimi_heater_mc2_54_48_e6_89_5f_4f
m_ioana_min_temp_entity_id = dataget("ioana_min_temp_entity_id") #input_number.min_ioanas_bedroom_temperature
m_fabian_min_temp_entity_id = dataget("fabian_min_temp_entity_id")#input_number.min_fabians_bedroom_temperature
m_dining_min_temp_entity_id = dataget("dining_min_temp_entity_id")#input_number.min_dining_temperature
m_smallbedroom_min_temp_entity_id = dataget("smallbedroom_min_temp_entity_id")#input_number.min_small_bedroom_temperature
m_ioana_sleeps_in_her_room = dataget("input_boolean.ioana_sleeps_in_her_room")
m_thermostat_away_mode = dataget("input_boolean.thermostat_away_mode")

m_ioanas_smart_heater_entity_id = m_ioanas_smart_heater_entity_id if m_ioanas_smart_heater_entity_id is not None else "climate.zhimi_heater_mc2_54_48_e6_89_5f_4f"
m_ioana_min_temp_entity_id = m_ioana_min_temp_entity_id if m_ioana_min_temp_entity_id is not None else "input_number.min_ioanas_bedroom_temperature"
m_fabian_min_temp_entity_id = m_fabian_min_temp_entity_id if m_fabian_min_temp_entity_id is not None else "input_number.min_fabians_bedroom_temperature"
m_dining_min_temp_entity_id = m_dining_min_temp_entity_id if m_dining_min_temp_entity_id is not None else "input_number.min_dining_temperature"
m_smallbedroom_min_temp_entity_id = m_smallbedroom_min_temp_entity_id if m_smallbedroom_min_temp_entity_id is not None else "input_number.min_small_bedroom_temperature"
m_ioana_sleeps_in_her_room = m_ioana_sleeps_in_her_room if m_ioana_sleeps_in_her_room is not None else "input_boolean.ioana_sleeps_in_her_room"
m_thermostat_away_mode = m_thermostat_away_mode if m_thermostat_away_mode is not None else "input_boolean.thermostat_away_mode"


alldays=[0, 1, 2, 3, 4, 5, 6, 7]
weekdays=[0, 1, 2, 3, 4, 5]
weekend=[6, 7]

def IsWeekDay(timestamp: datetime):
       day =  timestamp.weekday()
       return day >=0 and day <=5

class TurnOnSmartHeater:
    def __init__(self, entity_id: string, temp: float) -> None:
        self.entity_id = entity_id
        self.temp = temp

    def Execute(self):

        if (stateget(self.entity_id) != "heat"):
            service_data = {"entity_id": self.entity_id}
            callService("climate", "turn_on", service_data)  

        if (float(stateget(self.entity_id+".temperature")) != self.temp):
            service_data = {"entity_id": self.entity_id, "temperature": self.temp}
            callService("climate", "set_temperature", service_data) 

class TurnOffSmartHeater:
    def __init__(self, entity_id: string) -> None:
        self.entity_id = entity_id

    def Execute(self):
        if (stateget(self.entity_id) != "off"):
            service_data = {"entity_id": self.entity_id}
            callService("climate", "turn_off", service_data)  

class SetTemperature:
    def __init__(self, entity_id: string, temp: float) -> None:
        self.entity_id = entity_id
        self.temp = temp
        
    def Execute(self):
        if (float(stateget(self.entity_id)) != self.temp):
            service_data = {"entity_id": self.entity_id, "value": float(self.temp)}
            callService("input_number", "set_value", service_data)

class TimeFrame:
    def __init__(self, name: string, day: int, hour: int, minute: int, actions):
        self.actions=actions
        self.name=name
        self.day=day
        self.time = datetime.time(hour, minute, 0, 0)
        self.endTime = self.time
        #loginfo(self.time)

    def Contains(self, tm: datetime):
        if self.time == self.endTime:
            return True
            
        if self.time <= self.endTime:
            return self.time<=tm.time() and tm.time()<self.endTime

        return self.time<=tm.time() or tm.time()<self.endTime

    def Execute(self):
        loginfo(self.name + " " + str(self.day) + " time:" + str(self.time))
        for a in self.actions:
            #loginfo(a)
            a.Execute()

class Room:
    def __init__(self, name: string):
        self.days = {}
        self.name=name

    def On(self, days, hour: int, minute: int, action):
        for d in days:
            if not d in self.days:
                #loginfo("Creating day " + str(d) + " " + str(len(self.days)))
                self.days[d] = []
            self.days[d].append(TimeFrame(self.name, d, hour, minute, action))
            self.days[d].sort(key=lambda x: x.time)
            timeframes = self.days[d]
            #loginfo(timeframes)
            i=0
            for t in timeframes:
                if (i<len(timeframes)-1):
                    timeframes[i].endTime=timeframes[i+1].time
                i=i+1
            timeframes[-1].endTime=timeframes[0].time

    def Execute(self, currenttime: datetime):
        loginfo("Processing " + self.name)

        weekday = currenttime.weekday()
        if (not weekday in self.days):
            return

        loginfo("Processing day " + str(weekday))
        for t in self.days[weekday]:
            if (t.Contains(currenttime)):
                loginfo(self.name)
                t.Execute()
                break

rooms = []

def BuildRooms():
    rooms.clear()
    #log.error("buildrooms")
    loginfo("####BuildRooms")
    
    if (stateget(m_thermostat_away_mode)=="on"):

        Ioana = Room("Ioana")
        Ioana.On(alldays, 8, 00, [TurnOffSmartHeater(m_ioanas_smart_heater_entity_id), SetTemperature(m_ioana_min_temp_entity_id, 16.0)])
        
        Fabian = Room("Fabian")
        Fabian.On(alldays, 8, 00, [SetTemperature(m_fabian_min_temp_entity_id, 18.0)])

        Dining = Room("Dining")
        Dining.On(alldays, 8, 00, [SetTemperature(m_dining_min_temp_entity_id, 18.0)])
        
        SmallBedroom = Room("SmallBedroom")
        SmallBedroom.On(alldays, 8, 00, [SetTemperature(m_smallbedroom_min_temp_entity_id, 16.0)])

        
        rooms.append(Ioana)
        rooms.append(Fabian)
        rooms.append(Dining)
        rooms.append(SmallBedroom)        

    else:
        Ioana = Room("Ioana")
        if (stateget(m_ioana_sleeps_in_her_room)=="on"):
            loginfo("####BuildRooms - Ioana ON")
            #Ioana.On(weekdays, 6, 45, [TurnOnSmartHeater(m_ioanas_smart_heater_entity_id, 21), SetTemperature(m_ioana_min_temp_entity_id, 21.0)])
            #Ioana.On(weekdays, 7, 20, [TurnOffSmartHeater(m_ioanas_smart_heater_entity_id), SetTemperature(m_ioana_min_temp_entity_id, 19.0)])
            Ioana.On(alldays, 9, 00, [TurnOffSmartHeater(m_ioanas_smart_heater_entity_id), SetTemperature(m_ioana_min_temp_entity_id, 20.5)])
            Ioana.On(alldays, 15, 00, [SetTemperature(m_ioana_min_temp_entity_id, 20.0)])
            Ioana.On(alldays, 22, 00, [TurnOnSmartHeater(m_ioanas_smart_heater_entity_id, 19), SetTemperature(m_ioana_min_temp_entity_id, 20.5)])
        else:
            loginfo("####BuildRooms - Ioana OFF")
            Ioana.On(alldays, 11, 45, [TurnOffSmartHeater(m_ioanas_smart_heater_entity_id), SetTemperature(m_ioana_min_temp_entity_id, 16.0)])
        
        Fabian = Room("Fabian")
        Fabian.On(weekdays, 6, 45, [SetTemperature(m_fabian_min_temp_entity_id, 22.5)])
        
        if (stateget(m_ioana_sleeps_in_her_room)=="on"):
            Fabian.On(weekdays, 7, 40, [SetTemperature(m_fabian_min_temp_entity_id, 17.0)])
        else:
            Fabian.On(weekdays, 7, 40, [SetTemperature(m_fabian_min_temp_entity_id, 21.5)])
        Fabian.On(weekdays, 13, 30, [SetTemperature(m_fabian_min_temp_entity_id, 21.5)])
        #Fabian.On([0, 4], 17, 00, [SetTemperature(m_fabian_min_temp_entity_id, 20.5)])
        #Fabian.On(alldays, 17, 30, [SetTemperature(m_fabian_min_temp_entity_id, 20.5)])
        Fabian.On(alldays, 22, 00, [SetTemperature(m_fabian_min_temp_entity_id, 21.0)])
        
        Dining = Room("Dining")
        Dining.On(weekdays, 7, 00, [SetTemperature(m_dining_min_temp_entity_id, 21.0)])
        Dining.On(weekdays, 7, 50, [SetTemperature(m_dining_min_temp_entity_id, 19.5)])
        Dining.On(weekdays, 9, 30, [SetTemperature(m_dining_min_temp_entity_id, 21.0)])
        Dining.On(weekdays, 11, 40, [SetTemperature(m_dining_min_temp_entity_id, 20.0)])
        Dining.On(weekdays, 13, 30, [SetTemperature(m_dining_min_temp_entity_id, 21.0)])
        Dining.On(alldays, 22, 00, [SetTemperature(m_dining_min_temp_entity_id, 16.0)])
        
        SmallBedroom = Room("SmallBedroom")
        SmallBedroom.On(alldays, 8, 00, [SetTemperature(m_smallbedroom_min_temp_entity_id, 16.0)])
        SmallBedroom.On(alldays, 22, 00, [SetTemperature(m_smallbedroom_min_temp_entity_id, 19.5)])
        
        
        rooms.append(Ioana)
        rooms.append(Fabian)
        rooms.append(Dining)
        rooms.append(SmallBedroom)
        
BuildRooms()

@service
@time_trigger
@time_trigger("once(06:45:00)", "once(07:00:00)", "once(07:20:00)", "once(07:30:00)", "once(07:40:00)", "once(07:50:00)", "once(08:00:00)", "once(09:30:00)", "once(10:00:00)", "once(11:40:00)", "once(13:30:00)", "once(15:00:00)", "once(22:00:00)", "once(23:45:00)")
@state_trigger("input_boolean.ioana_sleeps_in_her_room")
@state_trigger("input_boolean.thermostat_away_mode")
def thermostat_update():
    #log.error("pyscript thermostat started")
    BuildRooms()
    for r in rooms:
        r.Execute(datetime.datetime.now())

@service
def thermostat_update_explicit(ioanas_smart_heater_entity_id="climate.zhimi_heater_mc2_54_48_e6_89_5f_4f", ioana_min_temp_entity_id="input_number.min_ioanas_bedroom_temperature", fabian_min_temp_entity_id="input_number.min_fabians_bedroom_temperature", dining_min_temp_entity_id="input_number.min_dining_temperature", smallbedroom_min_temp_entity_id="input_number.min_small_bedroom_temperature", ioana_sleeps_in_her_room="input_boolean.ioana_sleeps_in_her_room"):
    """yaml
    description: Recalculates the thwermostat temperatures.
    fields:
        ioanas_smart_heater_entity_id:
            description: Id of Ioana's smart heater
            example: climate.zhimi_heater_mc2_54_48_e6_89_5f_4f
        ioana_min_temp_entity_id:
            description: input_number.min_ioanas_bedroom_temperature
            example: input_number.min_ioanas_bedroom_temperature
        fabian_min_temp_entity_id:
            example: input_number.min_fabians_bedroom_temperature
        dining_min_temp_entity_id:
            example: input_number.min_dining_temperature
        smallbedroom_min_temp_entity_id:
            example: input_number.min_small_bedroom_temperature     
        ioana_sleeps_in_her_room:
            example: input_boolean.ioana_sleeps_in_her_room            
    """    
    m_ioanas_smart_heater_entity_id = ioanas_smart_heater_entity_id
    m_ioana_min_temp_entity_id = ioana_min_temp_entity_id
    m_fabian_min_temp_entity_id = fabian_min_temp_entity_id
    m_dining_min_temp_entity_id = dining_min_temp_entity_id
    m_smallbedroom_min_temp_entity_id = smallbedroom_min_temp_entity_id
    m_ioana_sleeps_in_her_room = "input_boolean.ioana_sleeps_in_her_room"
    BuildRooms()
    for r in rooms:
        r.Execute(datetime.datetime.now())        
     