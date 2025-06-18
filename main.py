import asyncio
import os
import argparse # For command-line arguments
import sys # For sys.stdout.flush()
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto, DocumentAttributeFilename
from telethon.errors import SessionPasswordNeededError

# --- Configurações (Preencha com seus dados) ---
API_ID = 0000000000000000
API_HASH = '0ae000000000000000'
PHONE_NUMBER = '+5551999999999'
TARGET_CHANNEL_INPUT = -1000000000000

DOWNLOAD_FOLDER = 'downloads'
HISTORY_FILE = 'downloaded_history.txt'
SESSION_NAME = 'my_telegram_session'

CHECK_INTERVAL_SECONDS = 300
MESSAGES_FETCH_LIMIT_MONITORING = 50
MESSAGES_FETCH_LIMIT_HISTORICAL = 200
# --- Fim das Configurações ---

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

downloaded_ids = set()
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, 'r') as f:
        for line in f:
            try:
                downloaded_ids.add(int(line.strip()))
            except ValueError:
                print(f"Aviso: Linha inválida no arquivo de histórico ignorada: {line.strip()}")

def save_to_history(message_id):
    downloaded_ids.add(message_id)
    with open(HISTORY_FILE, 'a') as f:
        f.write(f"{message_id}\n")

def get_original_filename(message_obj, fallback_id):
    """Tries to get a sensible original filename."""
    if message_obj.file and hasattr(message_obj.file, 'name') and message_obj.file.name:
        return message_obj.file.name
    if message_obj.document:
        for attr in message_obj.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                return attr.file_name
    ext = ".dat"
    if message_obj.photo:
        ext = ".jpg"
    elif message_obj.document:
        mime_type = getattr(message_obj.document, 'mime_type', '')
        if 'zip' in mime_type: ext = ".zip"
        elif 'pdf' in mime_type: ext = ".pdf"
        elif 'text' in mime_type: ext = ".txt"
    return f"telegram_file_{fallback_id}{ext}"


async def download_media_from_message(client, message_obj, message_id_val, path_to_save, on_fly_mode=False, domains_to_scope=None):
    if message_id_val in downloaded_ids:
        return False

    is_document = isinstance(message_obj.media, MessageMediaDocument)
    is_photo = isinstance(message_obj.media, MessageMediaPhoto)

    if not (is_document or is_photo):
        return False

    media_type_str = "documento" if is_document else "foto"
    original_filename = get_original_filename(message_obj, message_id_val)

    if on_fly_mode and domains_to_scope and is_document:
        # On-fly processing for documents
        short_domain_list = ', '.join(list(domains_to_scope)[:3]) + ('...' if len(domains_to_scope) > 3 else '')
        print(f"  -> Processando '--onfly' para {media_type_str} ID {message_id_val} ({original_filename}). Escopo: [{short_domain_list}]")
        
        base, ext = os.path.splitext(original_filename)
        scoped_filename = f"{base}_scope{ext if ext else '.txt'}"
        scoped_filepath = os.path.join(path_to_save, scoped_filename)
        
        match_found_for_file = False
        lines_written_to_file = 0
        
        try:
            with open(scoped_filepath, 'w', encoding='utf-8', errors='ignore') as outfile:
                buffer = b''
                async for chunk in client.iter_download(message_obj.media):
                    if not chunk: continue
                    buffer += chunk
                    
                    while True: # Process all complete lines in the current buffer
                        try:
                            line_bytes, separator, rest_buffer = buffer.partition(b'\n')
                        except ValueError: # Should not happen with partition
                            break 

                        if separator: # A full line (terminated by newline) is found
                            buffer = rest_buffer # Keep the rest for the next iteration
                            line_str = line_bytes.decode('utf-8', errors='ignore')
                            
                            # Case-insensitive check for any domain
                            if any(domain.lower() in line_str.lower() for domain in domains_to_scope):
                                if not match_found_for_file: # First match for this file, print header
                                    print(f"     [+] Escopo encontrado em '{original_filename}':")
                                    match_found_for_file = True

                                # Output to terminal immediately
                                terminal_output = f"       | {line_str}"
                                print(terminal_output)
                                sys.stdout.flush() # Ensure terminal output is immediate

                                # Write to scope file and flush
                                outfile.write(line_str + '\n')
                                outfile.flush() # Ensure file output is immediate
                                lines_written_to_file +=1
                        else:
                            # No newline found in the current buffer part being processed (line_bytes is the whole buffer)
                            # Break inner loop and wait for more chunks
                            break 
                
                # After the loop, process any remaining data in the buffer (if the file doesn't end with a newline)
                if buffer: 
                    line_str = buffer.decode('utf-8', errors='ignore')
                    if any(domain.lower() in line_str.lower() for domain in domains_to_scope):
                        if not match_found_for_file:
                            print(f"     [+] Escopo encontrado em '{original_filename}' (final do arquivo):")
                            match_found_for_file = True
                        
                        terminal_output = f"       | {line_str}"
                        print(terminal_output)
                        sys.stdout.flush()

                        outfile.write(line_str + '\n') # Add a newline for consistency
                        outfile.flush()
                        lines_written_to_file += 1

            if match_found_for_file:
                print(f"     -> Concluído. Escopo salvo em: {scoped_filepath} ({lines_written_to_file} linha(s))")
                save_to_history(message_id_val)
                return True
            else:
                print(f"     -> Concluído. Nenhum escopo correspondente em {original_filename}. Arquivo _scope removido.")
                if os.path.exists(scoped_filepath):
                    try: os.remove(scoped_filepath)
                    except OSError as e: print(f"     Aviso: Não foi possível remover {scoped_filepath}: {e}")
                return False
        except Exception as e:
            print(f"     Erro CRÍTICO ao processar '--onfly' para {original_filename} (ID {message_id_val}): {e}")
            if 'scoped_filepath' in locals() and os.path.exists(scoped_filepath):
                try: os.remove(scoped_filepath); print(f"     Arquivo _scope parcial {scoped_filepath} removido devido a erro.")
                except OSError as ose: print(f"     Aviso: Não foi possível remover {scoped_filepath} após erro: {ose}")
            return False

    else:
        file_path_to_save = os.path.join(path_to_save, original_filename)
        try:
            print(f"  -> Baixando FULL {media_type_str} da mensagem ID {message_id_val} ({original_filename})...")
            downloaded_path = await message_obj.download_media(file=file_path_to_save)
            if downloaded_path:
                print(f"     Arquivo salvo em: {downloaded_path}")
                save_to_history(message_id_val)
                return True
            else:
                print(f"     Falha ao baixar mídia da mensagem {message_id_val} (caminho não retornado).")
        except Exception as e:
            print(f"     Erro ao baixar arquivo da mensagem {message_id_val}: {e}")
        return False


async def process_historical_messages(client, channel_entity, on_fly_mode, domains_to_scope):
    print(f"\n--- Iniciando Varredura Histórica de Mensagens em '{getattr(channel_entity, 'title', channel_entity.id)}' ---")
    total_messages_fetched = 0
    processed_count = 0
    last_id = 0

    while True:
        print(f"Buscando lote de mensagens históricas (a partir de ID aprox: {last_id if last_id else 'mais recentes'})...")
        history = await client.get_messages(channel_entity, limit=MESSAGES_FETCH_LIMIT_HISTORICAL, offset_id=last_id, reverse=False)
        
        if not history:
            print("Nenhuma mensagem mais antiga encontrada.")
            break

        print(f"Processando {len(history)} mensagens do lote...")
        for message in history:
            total_messages_fetched += 1
            if message.media:
                if await download_media_from_message(client, message, message.id, DOWNLOAD_FOLDER, on_fly_mode, domains_to_scope):
                    processed_count += 1
        
        if len(history) < MESSAGES_FETCH_LIMIT_HISTORICAL:
             print("Provavelmente final do histórico.")
             break
        last_id = history[-1].id

    print(f"--- Varredura Histórica Concluída ---")
    print(f"Total de mensagens verificadas: {total_messages_fetched}")
    print(f"{processed_count} novo(s) arquivo(s) processado(s) (baixado/escopo gerado).")


async def monitor_new_messages(client, channel_entity, on_fly_mode, domains_to_scope):
    print(f"\n--- Iniciando Modo de Monitoramento Contínuo ---")
    while True:
        print(f"\nVerificando novas mensagens em '{getattr(channel_entity, 'title', channel_entity.id)}'...")
        processed_in_cycle = 0
        
        seen_in_this_monitoring_batch = set() 
        async for message in client.iter_messages(channel_entity, limit=MESSAGES_FETCH_LIMIT_MONITORING):
            if message.id in downloaded_ids or message.id in seen_in_this_monitoring_batch:
                # Stop if we hit an already processed message; assumes messages newer than this one are also processed.
                # This makes sense for polling where we expect to see new messages first.
                break 
            
            seen_in_this_monitoring_batch.add(message.id)
            if message.media:
                if await download_media_from_message(client, message, message.id, DOWNLOAD_FOLDER, on_fly_mode, domains_to_scope):
                    processed_in_cycle += 1
        
        if processed_in_cycle == 0:
            print("Nenhum arquivo novo processado neste ciclo.")
        else:
            print(f"{processed_in_cycle} novo(s) arquivo(s) processado(s) neste ciclo.")

        print(f"Aguardando {CHECK_INTERVAL_SECONDS // 60}m {CHECK_INTERVAL_SECONDS % 60}s para próxima verificação...")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def load_domains(scope_str, scope_file_path):
    domains = set()
    if scope_str:
        domains.update([d.strip().lower() for d in scope_str.split(',') if d.strip()])
    
    if scope_file_path:
        try:
            with open(scope_file_path, 'r', encoding='utf-8') as f: # Specify encoding
                domains.update([line.strip().lower() for line in f if line.strip() and not line.startswith('#')])
        except FileNotFoundError:
            print(f"Aviso: Arquivo de escopo '{scope_file_path}' não encontrado.")
        except Exception as e:
            print(f"Aviso: Erro ao ler arquivo de escopo '{scope_file_path}': {e}")
            
    if domains:
        print(f"Escopos carregados ({len(domains)}): {list(domains)[:5]}{'...' if len(domains) > 5 else ''}")
    return domains if domains else None


async def main():
    parser = argparse.ArgumentParser(description="Telegram Downloader com opção de escopo on-the-fly.")
    parser.add_argument('--onfly', action='store_true', help="Habilita o processamento on-the-fly. Não baixa o arquivo original se escopos forem encontrados em documentos.")
    parser.add_argument('-s', '--scope', type=str, help="Lista de domínios separados por vírgula (ex: example.com,test.org).")
    parser.add_argument('-sf', '--scope-file', type=str, help="Caminho para arquivo com um domínio por linha.")
    
    args = parser.parse_args()

    domains_to_scope = load_domains(args.scope, args.scope_file)
    on_fly_active = False

    if args.onfly:
        if domains_to_scope:
            print("Modo --onfly ATIVADO. Filtrará documentos em tempo real.")
            on_fly_active = True
        else:
            print("Aviso: --onfly especificado, mas nenhum escopo fornecido (-s ou -sf). --onfly será IGNORADO.")
    elif domains_to_scope:
         print("Aviso: Domínios de escopo fornecidos, mas --onfly NÃO está ativo. Baixará arquivos completos.")

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    print("Iniciando o Userbot Downloader...")
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("Autenticação necessária.")
            try:
                await client.send_code_request(PHONE_NUMBER)
            except Exception as e:
                print(f"Erro ao enviar código: {e}. Tente novamente mais tarde.")
                return

            signed_in = False
            while not signed_in:
                code = input('Digite o código recebido: ')
                try:
                    await client.sign_in(PHONE_NUMBER, code)
                    signed_in = True
                    print("Login com código OK!")
                except SessionPasswordNeededError:
                    password_2fa = input('Senha 2FA: ')
                    try:
                        await client.sign_in(password=password_2fa)
                        signed_in = True
                        print("Login com 2FA OK!")
                    except Exception as e_pw:
                        print(f"Erro login 2FA: {e_pw}. Reinicie.")
                        return
                except Exception as e:
                    print(f"Erro login: {e}. Tente código novamente. Se persistir, reinicie.")
            if not signed_in: print("Falha na autenticação."); return
        else:
            print("Login OK (sessão existente).")

        try:
            target_entity_input = TARGET_CHANNEL_INPUT
            if isinstance(TARGET_CHANNEL_INPUT, str) and TARGET_CHANNEL_INPUT.startswith("-100"):
                try: target_entity_input = int(TARGET_CHANNEL_INPUT)
                except ValueError: print(f"Aviso: TARGET_CHANNEL_INPUT '{TARGET_CHANNEL_INPUT}' parece numérico mas falhou conversão.")
            
            channel_entity = await client.get_entity(target_entity_input)
            print(f"Canal/Chat encontrado: {getattr(channel_entity, 'title', target_entity_input)}")
        except Exception as e:
            print(f"Erro ao obter entidade do canal '{TARGET_CHANNEL_INPUT}': {e}. Verifique o ID/username."); return

        await process_historical_messages(client, channel_entity, on_fly_active, domains_to_scope)
        await monitor_new_messages(client, channel_entity, on_fly_active, domains_to_scope)

    except Exception as e:
        print(f"Erro inesperado: {e}")
    finally:
        if client.is_connected():
            print("Desconectando cliente...")
            await client.disconnect()
            print("Cliente desconectado.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
    except Exception as e:
        print(f"Erro fatal não capturado: {e}")
