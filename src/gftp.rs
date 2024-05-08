use anyhow::{anyhow, Context, Error, Result};
use futures::lock::Mutex;
use futures::prelude::*;
use rand::distributions::Alphanumeric;
use rand::Rng;
use serde::Serialize;
use sha3::{Digest, Sha3_256};
use std::collections::VecDeque;
use std::fs::{File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::Path;
use std::str::FromStr;
use std::sync::Arc;
use std::{fs, io};
use url::{quirks::hostname, Position, Url};

use ya_core_model::gftp as model;
use ya_core_model::identity;
use ya_core_model::net::{RemoteEndpoint, TryRemoteEndpoint};
use ya_core_model::NodeId;
use ya_service_bus::{typed as bus, RpcEndpoint};

pub const DEFAULT_CHUNK_SIZE: u64 = 40 * 1024;

// =========================================== //
// File download - publisher side ("requestor")
// =========================================== //

#[derive(Debug, Clone, Eq)]
pub struct StreamProgress {
    pub total: u64,
    pub current: u64,
    pub start: std::time::Instant,
    pub upload_list: VecDeque<u64>,
}
impl Default for StreamProgress {
    fn default() -> Self {
        StreamProgress {
            total: 0,
            current: 0,
            start: std::time::Instant::now(),
            upload_list: VecDeque::new(),
        }
    }
}

#[derive(Serialize)]
pub struct StreamProgressInfo {
    #[serde(rename = "cur")]
    pub current: u64,
    #[serde(rename = "tot")]
    pub total: u64,
    #[serde(rename = "elp")]
    pub elapsed: u64,
    #[serde(rename = "spc")]
    pub speed_curr: u64,
    #[serde(rename = "spt")]
    pub speed_total: u64,
}

impl PartialEq for StreamProgress {
    fn eq(&self, other: &Self) -> bool {
        let simple_field_res =
            self.total == other.total && self.current == other.current && self.start == other.start;
        if !simple_field_res {
            return false;
        }
        if self.upload_list.len() > 1 && other.upload_list.len() > 1 {
            let self_last = self.upload_list.iter().last().unwrap();
            let other_last = other.upload_list.iter().last().unwrap();
            let self_first = self.upload_list.iter().next().unwrap();
            let other_first = other.upload_list.iter().next().unwrap();
            return self_last == other_last && self_first == other_first;
        }
        self.upload_list.len() == other.upload_list.len()
    }
}

struct FileDesc {
    hash: String,
    file: Mutex<fs::File>,
    meta: model::GftpMetadata,

    upload_progress: Arc<parking_lot::Mutex<StreamProgress>>,
}

impl FileDesc {
    fn new(file: fs::File, hash: String, meta: model::GftpMetadata) -> Arc<Self> {
        let file = Mutex::new(file);

        Arc::new(FileDesc {
            hash,
            file,
            meta,
            upload_progress: Arc::new(parking_lot::Mutex::new(StreamProgress::default())),
        })
    }

    pub fn open(path: &Path) -> Result<Arc<FileDesc>> {
        let mut file =
            fs::File::open(path).with_context(|| format!("Can't open file {}", path.display()))?;

        let hash = hash_file_sha256(&mut file)?;
        let meta = model::GftpMetadata {
            file_size: file.metadata()?.len(),
        };

        Ok(FileDesc::new(file, hash, meta))
    }

    pub fn bind_handlers(self: &Arc<Self>) {
        let gsb_address = model::file_bus_id(&self.hash);
        let desc = self.clone();

        let upload_progress = self.upload_progress.clone();
        let _ = bus::bind(&gsb_address, move |_msg: model::GetMetadata| {
            log::debug!("Sending metadata: {:?}", desc.meta);
            let mut upload_progress_obj = upload_progress.lock();
            upload_progress_obj.total = desc.meta.file_size;
            upload_progress_obj.current = 0;
            upload_progress_obj.start = std::time::Instant::now();
            upload_progress_obj.upload_list.clear();
            future::ok(desc.meta.clone())
        });

        let desc = self.clone();
        let upload_progress = self.upload_progress.clone();
        let _ = bus::bind(&gsb_address, move |msg: model::GetChunk| {
            let desc = desc.clone();
            //log::info!("Sending chunk: {:?}", msg);
            let upload_progress = upload_progress.clone();
            async move {
                let chunk = desc.get_chunk(msg.offset, msg.size).await;
                match chunk {
                    Ok(chunk) => {
                        let mut upload_progress_obj = upload_progress.lock();
                        upload_progress_obj.total = desc.meta.file_size;
                        upload_progress_obj.current = chunk.offset + chunk.content.len() as u64;
                        Ok(chunk)
                    }
                    Err(error) => Err(error),
                }
            }
        });

        let upload_progress = self.upload_progress.clone();
        tokio::spawn(async move { report_progress_loop(upload_progress).await });
    }

    async fn get_chunk(
        &self,
        offset: u64,
        chunk_size: u64,
    ) -> Result<model::GftpChunk, model::Error> {
        let bytes_to_read = if self.meta.file_size - offset < chunk_size {
            self.meta.file_size - offset
        } else {
            chunk_size
        } as usize;

        log::debug!("Reading chunk at offset: {}, size: {}", offset, chunk_size);
        let mut buffer = vec![0u8; bytes_to_read];
        {
            let mut file = self.file.lock().await;

            file.seek(SeekFrom::Start(offset)).map_err(|error| {
                model::Error::ReadError(format!("Can't seek file at offset {}, {}", offset, error))
            })?;

            file.read_exact(&mut buffer).map_err(|error| {
                model::Error::ReadError(format!(
                    "Can't read {} bytes at offset {}, error: {}",
                    bytes_to_read, offset, error
                ))
            })?;
        }

        Ok(model::GftpChunk {
            offset,
            content: buffer,
        })
    }
}

pub async fn publish(path: &Path) -> Result<Url> {
    let filedesc = FileDesc::open(path)?;
    filedesc.bind_handlers();

    gftp_url(&filedesc.hash).await
}

pub async fn close(url: &Url) -> Result<bool> {
    let hash_name = match url.path_segments() {
        Some(segments) => match segments.last() {
            Some(segment) => segment,
            _ => return Err(anyhow!("Invalid URL: {:?}", url)),
        },
        _ => return Err(anyhow!("Invalid URL: {:?}", url)),
    };

    bus::unbind(model::file_bus_id(hash_name).as_str())
        .await
        .map_err(|e| anyhow!(e))
}

// =========================================== //
// File download - client side ("provider")
// =========================================== //

pub async fn download_from_url(url: &Url, dst_path: &Path) -> Result<()> {
    let (node_id, hash) = extract_url(url)?;
    download_file(node_id, &hash, dst_path).await
}

pub async fn report_progress_loop(progress: Arc<parking_lot::Mutex<StreamProgress>>) {
    let mut interval = tokio::time::interval(tokio::time::Duration::from_millis(250));
    let mut last_progress = progress.lock().clone();

    loop {
        interval.tick().await;
        let current = progress.lock().current;
        let progress = {
            let mut upload_obj = progress.lock();
            upload_obj.upload_list.push_back(current);
            if upload_obj.upload_list.len() > 20 {
                upload_obj.upload_list.pop_front();
            }
            upload_obj.clone()
        };

        if last_progress != progress && progress.total > 0 {
            let sec_el = progress.start.elapsed().as_secs_f64();
            let speed = if sec_el > 0_f64 {
                progress.current as f64 / sec_el
            } else {
                0.0
            };

            let current_speed = if progress.upload_list.len() >= 2 {
                (progress.upload_list.iter().last().unwrap()
                    - progress.upload_list.iter().next().unwrap()) as f64
                    / (progress.upload_list.len() - 1) as f64
                    / interval.period().as_secs_f64()
            } else {
                0_f64
            };

            let stream_progress_info = StreamProgressInfo {
                current: progress.current,
                total: progress.total,
                elapsed: sec_el as u64,
                speed_curr: current_speed as u64,
                speed_total: speed as u64,
            };

            println!("{}", serde_json::to_string(&stream_progress_info).unwrap());
        }
        last_progress = progress;
    }
}

pub async fn download_file(node_id: NodeId, hash: &str, dst_path: &Path) -> Result<()> {
    let remote = node_id.service_transfer(&model::file_bus_id(hash));
    log::debug!("Creating target file {}", dst_path.display());

    let mut file = create_dest_file(dst_path)?;

    log::debug!("Loading file {} metadata.", dst_path.display());
    let metadata = remote.send(model::GetMetadata {}).await??;

    log::debug!("Metadata: file size {}.", metadata.file_size);

    let chunk_size = DEFAULT_CHUNK_SIZE;
    let num_chunks = (metadata.file_size + (chunk_size - 1)) / chunk_size; // Divide and round up.

    file.set_len(metadata.file_size)?;

    let download_progress_ = Arc::new(parking_lot::Mutex::new(StreamProgress::default()));

    download_progress_.lock().total = metadata.file_size;

    let download_progress = download_progress_.clone();

    tokio::spawn(async move { report_progress_loop(download_progress).await });

    let download_progress = download_progress_.clone();
    futures::stream::iter(0..num_chunks)
        .map(|chunk_number| {
            remote.call(model::GetChunk {
                offset: chunk_number * chunk_size,
                size: chunk_size,
            })
        })
        .buffered(12)
        .map_err(anyhow::Error::from)
        .try_for_each(move |result| {
            future::ready((|| {
                let chunk = result?;
                download_progress.lock().current = chunk.offset + chunk.content.len() as u64;
                file.write_all(&chunk.content[..])?;
                Ok(())
            })())
        })
        .await?;

    Ok(())
}

// =========================================== //
// File upload - publisher side ("requestor")
// =========================================== //

pub async fn open_for_upload(filepath: &Path) -> Result<Url> {
    let hash_name = rand::thread_rng()
        .sample_iter(&Alphanumeric)
        .map(char::from)
        .take(65)
        .collect::<String>();

    let receive_progress_ = Arc::new(parking_lot::Mutex::new(StreamProgress::default()));
    let receive_progress = receive_progress_.clone();
    let file = Arc::new(Mutex::new(create_dest_file(filepath)?));

    let gsb_address = model::file_bus_id(&hash_name);
    let file_clone = file.clone();
    log::info!("Binding to GSB address: {}", gsb_address);
    let _ = bus::bind(&gsb_address, move |msg: model::UploadChunk| {
        let file = file_clone.clone();
        let receive_progress = receive_progress.clone();
        let chunk_offset = msg.chunk.offset;
        let chunk_size = msg.chunk.content.len() as u64;
        async move {
            let res = chunk_uploaded(file.clone(), msg).await;
            {
                let mut receive_progress_obj = receive_progress.lock();
                if chunk_offset == 0 {
                    receive_progress_obj.start = std::time::Instant::now();
                    receive_progress_obj.upload_list.clear();
                }
                receive_progress_obj.current = chunk_offset + chunk_size;
                receive_progress_obj.total = receive_progress_obj.current;
            }
            res
        }
    });
    let receive_progress = receive_progress_.clone();
    tokio::spawn(async move { report_progress_loop(receive_progress).await });

    let file_clone = file.clone();
    let _ = bus::bind(&gsb_address, move |msg: model::UploadFinished| {
        let file = file_clone.clone();
        async move { upload_finished(file.clone(), msg).await }
    });

    gftp_url(&hash_name).await
}

async fn chunk_uploaded(
    file: Arc<Mutex<File>>,
    msg: model::UploadChunk,
) -> Result<(), model::Error> {
    let mut file = file.lock().await;
    let chunk = msg.chunk;

    file.seek(SeekFrom::Start(chunk.offset)).map_err(|error| {
        model::Error::ReadError(format!(
            "Can't seek file at offset {}, {}",
            chunk.offset, error
        ))
    })?;
    file.write_all(&chunk.content[..]).map_err(|error| {
        model::Error::WriteError(format!(
            "Can't write {} bytes at offset {}, error: {}",
            chunk.content.len(),
            chunk.offset,
            error
        ))
    })?;
    Ok(())
}

async fn upload_finished(
    file: Arc<Mutex<File>>,
    msg: model::UploadFinished,
) -> Result<(), model::Error> {
    let mut file = file.lock().await;
    file.flush()
        .map_err(|error| model::Error::WriteError(format!("Can't flush file: {}", error)))?;

    if let Some(expected_hash) = msg.hash {
        log::debug!("Upload finished. Verifying hash...");

        let real_hash = hash_file_sha256(&mut file)
            .map_err(|error| model::Error::InternalError(error.to_string()))?;

        if expected_hash != real_hash {
            log::debug!(
                "Uploaded file hash {} is different than expected hash {}.",
                &real_hash,
                &expected_hash
            );
            //TODO: We should notify publisher about not matching hash.
            //      Now we send error only for uploader.
            return Err(model::Error::IntegrityError);
        }
        log::debug!("File hash matches expected hash {}.", &expected_hash);
        println!(
            "Upload finished correctly. File hash matches expected hash {}.",
            &expected_hash
        );
        println!("Press Ctrl+C to exit.");
    } else {
        log::debug!("Upload finished. Expected file hash not provided. Omitting validation.");
    }

    //TODO: unsubscribe gsb events.
    Ok(())
}

// =========================================== //
// File upload - client side ("provider")
// =========================================== //

pub async fn upload_file(path: &Path, url: &Url) -> Result<()> {
    let (node_id, random_filename) = extract_url(url)?;
    let remote = node_id.try_service(&model::file_bus_id(&random_filename))?;

    log::debug!("Opening file to send {}.", path.display());

    let chunk_size = DEFAULT_CHUNK_SIZE;

    let upload_progress_ = Arc::new(parking_lot::Mutex::new(StreamProgress::default()));

    let upload_progress = upload_progress_.clone();
    tokio::spawn(async move { report_progress_loop(upload_progress).await });
    let upload_progress = upload_progress_.clone();
    let (file_size, chunks) = get_chunks(path, chunk_size)?;
    upload_progress.lock().total = file_size;
    futures::stream::iter(chunks)
        .map(|chunk| {
            let upload_progress = upload_progress.clone();
            let remote = remote.clone();
            async move {
                let chunk = chunk?;
                let chunk_offset = chunk.offset;
                let chunk_size = chunk.content.len() as u64;
                let resp =
                    Ok::<_, anyhow::Error>(remote.call(model::UploadChunk { chunk }).await??);
                upload_progress.lock().current = chunk_offset + chunk_size;
                resp
            }
        })
        .buffered(3)
        .try_for_each(|_| future::ok(()))
        .await?;

    log::debug!("Computing file hash.");
    let hash = hash_file_sha256(&mut File::open(path)?)?;

    log::debug!("File [{}] has hash [{}].", path.display(), &hash);
    remote
        .call(model::UploadFinished { hash: Some(hash) })
        .await??;
    log::debug!("Upload finished correctly.");
    Ok(())
}

// =========================================== //
// Utils and common functions
// =========================================== //

fn get_chunks(
    file_path: &Path,
    chunk_size: u64,
) -> Result<
    (
        u64,
        impl Iterator<Item = Result<model::GftpChunk, std::io::Error>> + 'static,
    ),
    std::io::Error,
> {
    let mut file = OpenOptions::new().read(true).open(file_path)?;

    let file_size = file.metadata()?.len();
    let n_chunks = (file_size + chunk_size - 1) / chunk_size;

    Ok((
        file_size,
        (0..n_chunks).map(move |n| {
            let offset = n * chunk_size;
            let bytes_to_read = if offset + chunk_size > file_size {
                file_size - offset
            } else {
                chunk_size
            };
            let mut buffer = vec![0u8; bytes_to_read as usize];
            file.read_exact(&mut buffer)?;
            Ok(model::GftpChunk {
                offset,
                content: buffer,
            })
        }),
    ))
}

fn hash_file_sha256(mut file: &mut fs::File) -> Result<String> {
    let mut hasher = Sha3_256::new();

    file.seek(SeekFrom::Start(0))
        .with_context(|| "Can't seek file at offset 0.".to_string())?;
    io::copy(&mut file, &mut hasher)?;

    Ok(format!("{:x}", hasher.result()))
}

/// Returns NodeId and file hash from gftp url.
/// Note: In case of upload, hash is not real hash of file
/// but only cryptographically strong random string.
pub fn extract_url(url: &Url) -> Result<(NodeId, String)> {
    if url.scheme() != "gftp" {
        return Err(Error::msg(format!(
            "Unsupported url scheme {}.",
            url.scheme()
        )));
    }

    let node_id = NodeId::from_str(hostname(url))
        .with_context(|| format!("Url {} has invalid node_id.", url))?;

    // Note: Remove slash from beginning of path.
    let hash = &url[Position::BeforePath..Position::BeforeQuery][1..];
    Ok((node_id, hash.to_owned()))
}

async fn gftp_url(hash: &str) -> Result<Url> {
    let id = bus::service(identity::BUS_ID)
        .call(identity::Get::ByDefault)
        .await??
        .unwrap();

    Ok(Url::parse(&format!("gftp://{:?}/{}", id.node_id, hash))?)
}

fn ensure_dir_exists(file_path: &Path) -> Result<()> {
    if let Some(file_dir) = file_path.parent() {
        fs::create_dir_all(file_dir)?
    }
    Ok(())
}

fn create_dest_file(file_path: &Path) -> Result<File> {
    ensure_dir_exists(file_path).with_context(|| {
        format!(
            "Can't create destination directory for file: [{}].",
            file_path.display()
        )
    })?;
    OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(true)
        .open(file_path)
        .with_context(|| format!("Can't create destination file: [{}].", file_path.display()))
}
