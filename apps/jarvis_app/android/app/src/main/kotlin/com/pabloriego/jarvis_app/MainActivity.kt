package com.pabloriego.jarvis_app

import android.app.AlertDialog
import android.content.Intent
import android.database.sqlite.SQLiteDatabase
import android.net.Uri
import android.os.BatteryManager
import android.os.StatFs
import android.provider.DocumentsContract
import androidx.documentfile.provider.DocumentFile
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.Executors

class MainActivity : FlutterActivity() {
    private var picker: MethodChannel.Result? = null
    private val worker = Executors.newSingleThreadExecutor()
    private lateinit var database: SQLiteDatabase
    private val maxBytes = 10 * 1024 * 1024

    override fun configureFlutterEngine(engine: FlutterEngine) {
        super.configureFlutterEngine(engine)
        database = openOrCreateDatabase("jarvis-local.sqlite3", MODE_PRIVATE, null)
        database.execSQL("CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY,content TEXT NOT NULL,revision INTEGER NOT NULL,deleted INTEGER DEFAULT 0,updated INTEGER NOT NULL)")
        database.execSQL("CREATE TABLE IF NOT EXISTS recovery(id TEXT PRIMARY KEY,name TEXT,tree_uri TEXT,parent_uri TEXT,sha TEXT,mime TEXT,created INTEGER)")
        database.execSQL("CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,digest TEXT NOT NULL,state TEXT NOT NULL,result TEXT)")
        database.version = 1
        MethodChannel(engine.dartExecutor.binaryMessenger, "jarvis/device").setMethodCallHandler { call, result ->
            when(call.method) {
                "remote.execute" -> {
                    val envelope=call.argument<Map<String,Any?>>("envelope") ?: emptyMap()
                    AlertDialog.Builder(this).setTitle("Solicitud remota a este teléfono")
                        .setMessage("${envelope["tool_name"]}\n${envelope["arguments"]}\n\nLos resultados se enviarán al backend emparejado.")
                        .setNegativeButton("Rechazar"){_,_->result.error("denied","Solicitud remota rechazada.",null)}
                        .setPositiveButton("Permitir una vez"){_,_->execute(call,result)}
                        .setOnCancelListener{result.error("cancelled","Solicitud cancelada.",null)}.show()
                }
                "files.chooseTree", "apps.installApk" -> {
                    if(picker != null) { result.error("busy","Ya hay un diálogo del sistema abierto.",null); return@setMethodCallHandler }
                    picker = result
                    val tree = call.method == "files.chooseTree"
                    val intent = Intent(if(tree) Intent.ACTION_OPEN_DOCUMENT_TREE else Intent.ACTION_OPEN_DOCUMENT)
                    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
                    if(!tree) { intent.type = "application/vnd.android.package-archive"; intent.addCategory(Intent.CATEGORY_OPENABLE) }
                    startActivityForResult(intent, if(tree) 901 else 902)
                }
                "apps.store" -> {
                    val pkg = call.argument<String>("package") ?: ""
                    if(!pkg.matches(Regex("[A-Za-z][A-Za-z0-9_.]+"))) { result.error("invalid_package","Indicá un paquete Android válido.",null); return@setMethodCallHandler }
                    try { startActivity(Intent(Intent.ACTION_VIEW,Uri.parse("https://play.google.com/store/apps/details?id=$pkg")));result.success(mapOf("status" to "opened")) }
                    catch(e:Exception){result.error("unavailable","No hay aplicación para abrir la tienda.",null)}
                }
                else -> {
                    val changes = call.method in setOf("files.create","files.write","files.copy","files.move","files.rename","files.trash","files.restore")
                    if(changes) {
                        val description = "Este teléfono\n${call.method}\n${call.argument<String>("name") ?: call.argument<String>("uri") ?: "Restaurar copia"}\n\n${call.argument<String>("content")?.take(2000) ?: ""}"
                        AlertDialog.Builder(this).setTitle("Confirmar operación local").setMessage(description)
                            .setNegativeButton("Cancelar") { _,_ -> result.error("cancelled","Operación cancelada sin despachar.",null) }
                            .setPositiveButton("Confirmar") { _,_ -> execute(call,result) }.setOnCancelListener { result.error("cancelled","Cancelado.",null) }.show()
                    } else execute(call,result)
                }
            }
        }
    }

    private fun execute(call: MethodCall, result: MethodChannel.Result) {
        worker.execute {
            try { val data = dispatch(call);runOnUiThread { result.success(data) } }
            catch(e:Exception){runOnUiThread { result.error("local_operation_failed", e.message ?: "No se pudo completar la operación.",null) }}
        }
    }
    private fun arg(call:MethodCall,key:String)=call.argument<String>(key) ?: throw IllegalArgumentException("Falta $key")
    private fun sha(bytes:ByteArray)=MessageDigest.getInstance("SHA-256").digest(bytes).joinToString(""){"%02x".format(it)}
    private fun read(uri:Uri):ByteArray {
        val data=contentResolver.openInputStream(uri)?.use { it.readNBytes(maxBytes+1) } ?: error("Documento no disponible.")
        require(data.size<=maxBytes){"Máximo 10 MiB por archivo."};return data
    }
    private fun resolve(tree:String,uri:String):DocumentFile {
        val treeUri=Uri.parse(tree)
        require(contentResolver.persistedUriPermissions.any { it.uri==treeUri && it.isReadPermission }) { "Permiso de carpeta revocado." }
        val root=DocumentFile.fromTreeUri(this,treeUri) ?: error("Carpeta no disponible.")
        if(uri==tree || uri==root.uri.toString())return root
        val target=Uri.parse(uri)
        require(target.authority==treeUri.authority && DocumentsContract.isChildDocument(contentResolver,root.uri,target)) { "Documento fuera de la carpeta autorizada." }
        return DocumentFile.fromSingleUri(this,target) ?: error("Documento no disponible.")
    }
    private fun writable(tree:String){require(contentResolver.persistedUriPermissions.any { it.uri.toString()==tree && it.isWritePermission }){"No hay permiso de escritura vigente."}}
    private fun checkVersion(call:MethodCall,file:DocumentFile):ByteArray {
        val data=read(file.uri);require(sha(data)==call.argument<String>("version")){"El archivo cambió. Leelo nuevamente antes de modificarlo."};return data
    }
    private fun info(f:DocumentFile)=mapOf("uri" to f.uri.toString(),"name" to (f.name?:"Documento"),"directory" to f.isDirectory,
        "size" to f.length(),"version" to if(f.isFile && f.length()<=maxBytes)sha(read(f.uri)) else null)
    private fun name(value:String):String { require(value.isNotBlank() && !value.contains('/') && !value.contains('\\') && value !in setOf(".","..")){"Nombre de archivo inválido."};return value }
    private fun preserve(file:DocumentFile,tree:String,parent:String,data:ByteArray):String {
        val id=UUID.randomUUID().toString();val dir=File(filesDir,"recovery");dir.mkdirs();val backup=File(dir,id);backup.writeBytes(data)
        require(sha(backup.readBytes())==sha(data)){"No se pudo verificar la copia recuperable."}
        database.execSQL("INSERT INTO recovery VALUES(?,?,?,?,?,?,?)",arrayOf<Any?>(id,file.name,tree,parent,sha(data),file.type,System.currentTimeMillis()))
        return id
    }
    private fun create(parent:DocumentFile,label:String,mime:String,data:ByteArray):DocumentFile {
        require(parent.isDirectory){"Seleccioná una carpeta destino."};require(parent.findFile(label)==null){"El destino existe; no se sobrescribió."}
        val dest=parent.createFile(mime,name(label)) ?: error("El proveedor no permite crear el archivo.")
        try { contentResolver.openOutputStream(dest.uri,"wt")!!.use{it.write(data)};require(sha(read(dest.uri))==sha(data)){"La copia no coincide con el original."} }
        catch(e:Exception){dest.delete();throw e};return dest
    }
    private fun dispatch(call:MethodCall):Any? {
        if(call.method=="remote.execute") {
            val envelope=call.argument<Map<String,Any?>>("envelope") ?: error("Falta el contrato remoto.")
            val rid=envelope["request_id"] as String
            val tool=envelope["tool_name"] as String
            val allowed=setOf("files.list","files.read","files.create","files.write","files.copy","files.move","files.rename","files.trash","files.restore","memory.list","memory.save","memory.delete","system.metrics")
            require(tool in allowed && envelope["schema_version"]==1){"Herramienta remota incompatible."}
            require((envelope["deadline"] as Number).toDouble()*1000>System.currentTimeMillis()){ "La solicitud remota venció." }
            val fingerprint=sha(org.json.JSONObject(envelope).toString().toByteArray())
            database.rawQuery("SELECT digest,state FROM requests WHERE id=?",arrayOf(rid)).use { c ->
                if(c.moveToFirst()) { require(c.getString(0)==fingerprint){"Reutilización inválida del identificador."};return mapOf("status" to "uncertain","user_message" to "Solicitud ya recibida. Revisá la evidencia local; no se repite.","retry_safe" to false) }
            }
            database.execSQL("INSERT INTO requests VALUES(?,?,'running',NULL)",arrayOf(rid,fingerprint))
            @Suppress("UNCHECKED_CAST")
            val args=(envelope["arguments"] as Map<String,Any?>).toMutableMap()
            if(envelope["expected_resource_version"]!=null)args["version"]=envelope["expected_resource_version"]
            val output=try { mapOf("status" to "completed","data" to dispatch(MethodCall(tool,args)),"retry_safe" to false,
                "evidence" to listOf(mapOf("platform" to "Android","request_id" to rid))) }
            catch(e:Exception){mapOf("status" to "uncertain","user_message" to (e.message?:"Error local"),"retry_safe" to false)}
            database.execSQL("UPDATE requests SET state='completed',result=? WHERE id=?",arrayOf(org.json.JSONObject(output).toString(),rid))
            return output
        }
        when(call.method){
            "memory.list" -> database.rawQuery("SELECT id,content,revision FROM memories WHERE deleted=0 AND instr(lower(content),lower(?))>0 ORDER BY updated DESC",arrayOf(call.argument<String>("query")?:"")).use { c ->
                val rows=mutableListOf<Map<String,Any>>();while(c.moveToNext())rows.add(mapOf("id" to c.getString(0),"content" to c.getString(1),"revision" to c.getInt(2)));return rows }
            "memory.save" -> {
                val id=call.argument<String>("id");val text=arg(call,"content");require(text.length<=8000){"Recuerdo demasiado largo."}
                if(id==null){val key=UUID.randomUUID().toString();database.execSQL("INSERT INTO memories VALUES(?,?,1,0,?)",arrayOf<Any>(key,text,System.currentTimeMillis()));return key}
                val values=android.content.ContentValues().apply{put("content",text);put("revision",(call.argument<Int>("revision")?:0)+1);put("updated",System.currentTimeMillis())}
                require(database.update("memories",values,"id=? AND revision=? AND deleted=0",arrayOf(id,call.argument<Int>("revision").toString()))==1){"Conflicto de revisión."};return id
            }
            "memory.delete" -> {
                val values=android.content.ContentValues().apply{put("content","");put("deleted",1);put("revision",(call.argument<Int>("revision")?:0)+1);put("updated",System.currentTimeMillis())}
                require(database.update("memories",values,"id=? AND revision=? AND deleted=0",arrayOf(arg(call,"id"),call.argument<Int>("revision").toString()))==1){"Conflicto de revisión."};return true
            }
            "system.metrics" -> {val disk=StatFs(filesDir.path);val battery=getSystemService(BATTERY_SERVICE) as BatteryManager
                return mapOf("device" to android.os.Build.MODEL,"battery_percent" to battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY),"disk_free" to disk.availableBytes,"disk_total" to disk.totalBytes)}
            "files.grants" -> return contentResolver.persistedUriPermissions.filter{it.isReadPermission}.map{mapOf("uri" to it.uri.toString(),"name" to (DocumentFile.fromTreeUri(this,it.uri)?.name?:"Carpeta"))}
            "files.revoke" -> {val uri=Uri.parse(arg(call,"tree"));val p=contentResolver.persistedUriPermissions.first{it.uri==uri};contentResolver.releasePersistableUriPermission(uri,(if(p.isReadPermission)Intent.FLAG_GRANT_READ_URI_PERMISSION else 0) or (if(p.isWritePermission)Intent.FLAG_GRANT_WRITE_URI_PERMISSION else 0));return true}
            "files.recovery" -> database.rawQuery("SELECT id,name,created FROM recovery ORDER BY created DESC",null).use { c -> val rows=mutableListOf<Map<String,Any>>();while(c.moveToNext())rows.add(mapOf("id" to c.getString(0),"name" to c.getString(1),"created" to c.getLong(2)));return rows }
            "files.restore" -> database.rawQuery("SELECT name,tree_uri,parent_uri,sha,mime FROM recovery WHERE id=?",arrayOf(arg(call,"id"))).use { c ->
                require(c.moveToFirst()){ "Copia no encontrada." };val tree=c.getString(1);writable(tree);val parent=resolve(tree,c.getString(2));val data=File(filesDir,"recovery/${arg(call,"id")}").readBytes();require(sha(data)==c.getString(3)){"Copia dañada."};return info(create(parent,c.getString(0),c.getString(4)?:"application/octet-stream",data)) }
        }
        val tree=arg(call,"tree");val uri=arg(call,"uri");val file=resolve(tree,uri)
        when(call.method){
            "files.list" -> return file.listFiles().take(500).map{info(it)}
            "files.read" -> {val data=read(file.uri);return mapOf("content" to Charsets.UTF_8.newDecoder().decode(java.nio.ByteBuffer.wrap(data)).toString(),"version" to sha(data))}
            "files.create" -> {writable(tree);return info(create(file,arg(call,"name"),"text/plain",arg(call,"content").toByteArray()))}
            "files.write" -> {
                writable(tree);val old=checkVersion(call,file);val parent=call.argument<String>("parent")?:tree
                val backup=preserve(file,tree,parent,old);val data=arg(call,"content").toByteArray();require(data.size<=maxBytes){"Archivo demasiado grande."}
                contentResolver.openOutputStream(file.uri,"wt")!!.use{it.write(data)};require(sha(read(file.uri))==sha(data)){"No se verificó la escritura. Hay una copia recuperable."}
                return mapOf("version" to sha(data),"backup_id" to backup,"atomic" to false)
            }
            "files.copy","files.move","files.rename" -> {
                writable(tree);val data=checkVersion(call,file);val parent=resolve(tree,arg(call,"parent"));val dest=create(parent,arg(call,"name"),file.type?:"application/octet-stream",data)
                if(call.method!="files.copy"){checkVersion(call,file);require(file.delete()){ "Copia creada; el origen no se pudo eliminar." }};return info(dest)
            }
            "files.trash" -> {writable(tree);val data=checkVersion(call,file);val id=preserve(file,tree,arg(call,"parent"),data);checkVersion(call,file);require(file.delete()){ "Se guardó copia, pero no se pudo eliminar el original." };return mapOf("backup_id" to id)}
            else -> error("Operación no soportada.")
        }
    }
    @Deprecated("Uses Android activity result for Flutter bridge")
    override fun onActivityResult(requestCode:Int,resultCode:Int,data:Intent?){
        super.onActivityResult(requestCode,resultCode,data)
        if(requestCode !in setOf(901,902))return
        val result=picker;picker=null
        val uri=data?.data
        if(resultCode!=RESULT_OK||uri==null){result?.error("cancelled","Selección cancelada.",null);return}
        try{
            if(requestCode==901){contentResolver.takePersistableUriPermission(uri,data.flags and (Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION));result?.success(uri.toString())}
            else{val intent=Intent(Intent.ACTION_VIEW).setDataAndType(uri,"application/vnd.android.package-archive").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);startActivity(intent);result?.success(mapOf("status" to "awaiting_system_installer","verified_installation" to false))}
        }catch(e:Exception){result?.error("system_permission",e.message,null)}
    }
    override fun onDestroy(){worker.shutdown();super.onDestroy()}
}
