import socket
import threading
import keyboard
import time
import json
import configparser
import requests
import pyautogui

def send_name_to_server(client_socket, name):
    client_socket.send(f'set_name:{name}'.encode('utf-8'))


def send_to_webhook(webhook_url, message):
    payload = {
        "content": message
    }
    response = requests.post(webhook_url, json=payload)
    if response.status_code == 204:
        print(f"Message sent to Discord webhook.")

def confirm_code_used(client_socket, code):
    client_socket.send(f'confirm_code:{code}'.encode('utf-8'))
    
    
def type_code(code, typing_delay):
    pyautogui.typewrite(code, interval=typing_delay)

def main():
    config = configparser.ConfigParser()
    config.read('config.ini')

    MASTER_SERVER_ADDRESS = (config['Server']['MASTER_SERVER_ADDRESS'], int(config['Server']['PORT']))
    TYPING_DELAY = float(config['Client']['TYPING_DELAY'])
    WEBHOOK_URL = config['Client']['WEBHOOK_URL']
    SECONDARY_WEBHOOK_URL = config['Client']['SECONDARY_WEBHOOK_URL']
    
    while True:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client_socket.connect(MASTER_SERVER_ADDRESS)
            print('Connected to Master Server')
            time.sleep(1)
            client_name = config['Client']['NAME']
            send_name_to_server(client_socket, client_name)

            current_codes = []
            used_codes = set()

            try:
                while True:
                    if len(current_codes) == 0:
                        request_data = 'get_codes'
                        client_socket.send(request_data.encode('utf-8'))
                        response_data = client_socket.recv(1024).decode('utf-8')
                        response_json = json.loads(response_data)

                        if 'codes' in response_json:
                            current_codes = response_json['codes']
                            print(f'Received codes from server: {current_codes}')

                    if keyboard.is_pressed('right'):
                        if current_codes:
                            current_code = current_codes.pop(0)
                            type_code(current_code, TYPING_DELAY)
                            used_codes.add(current_code)
                            print(f'Code {current_code} typed.')
                            confirm_code_used(client_socket, current_code)
                            message = f":key: {client_name} typed code: {current_code}"
                            send_to_webhook(WEBHOOK_URL, message)

                    elif keyboard.is_pressed('left'):
                        if used_codes:
                            last_used_code = used_codes.pop()
                            type_code(last_used_code, TYPING_DELAY)
                            print(f'Code {last_used_code} retyped.')

                    elif keyboard.is_pressed('down'):
                        if used_codes:
                            last_used_code = used_codes.pop()
                            message = f":red_circle: Requested to Approve from {client_name} code: {last_used_code}"
                            print(f'Message sent to secondary Discord webhook: {message}')
                            send_to_webhook(SECONDARY_WEBHOOK_URL, message)

                    time.sleep(0.1)

            except KeyboardInterrupt:
                pass
            finally:
                for code in used_codes:
                    confirm_code_used(client_socket, code)
        except ConnectionRefusedError:
            print('Connection to Master Server refused. Retrying in 5 seconds...')
            time.sleep(5)
        except ConnectionResetError:
            print('Connection forcibly closed by the remote host. Retrying in 5 seconds...')
            time.sleep(5)
        except KeyboardInterrupt:
            break
        finally:
            client_socket.close()

if __name__ == "__main__":
    main()
