import os
import subprocess
import config


def sanitize(filename):
    output = ''
    for c in filename:
        if c.isalnum():
            output += c
        else:
            output += '_'
    return output


def findFile(filename):
    for directory in config.directories:
        fullPath = directory + '/' + filename
        if os.path.isfile(fullPath):
            return fullPath
    return None

fileLayerCache = {}


def fileLayers(filename):
    if filename not in fileLayerCache:
        proc = os.popen("ogrinfo '%s' -al | grep -E '  Layer \(String\) = .*' | sed -e 's/  Layer (String) = //' | sort | uniq" % filename, "r")
        layers = []
        for line in proc:
            layer = line.strip("\n")
            if len(layer) > 0:
                layers.append(layer)
        proc.close()
        fileLayerCache[filename] = layers
    return fileLayerCache[filename]


def makeShapeFiles(sourceFile, layerName, outputTemplate, dest_dir):
    if sourceFile.lower()[-4:] != ".dxf":
        raise Exception("Unsupported source file format: '%s'" % sourceFile)

    base_path = os.path.dirname(os.path.abspath(__file__))
    variables = {'outputTemplate': os.path.join(dest_dir, outputTemplate),
                 'layerName': layerName,
                 'sourceFile': os.path.join(dest_dir, sourceFile),
                 'basePath': base_path}

    output = []
    output.append("""
ogr2ogr -skipfailures -where "LAYER = '{layerName}'" '{outputTemplate}-lines.shp' '{sourceFile}' -nlt LINESTRING 2>/dev/null
""".format(**variables))
    output.append("""
ogr2ogr -skipfailures -where "LAYER = '{layerName}'" '{outputTemplate}-areas.shp' '{sourceFile}' -nlt POLYGON 2>/dev/null
""".format(**variables))
    output.append("""
ogr2ogr -skipfailures -where "LAYER = '{layerName}'" '{outputTemplate}-points.shp' '{sourceFile}' -nlt POINT 2>/dev/null;
ogr2ogr -f CSV -skipfailures -sql 'SELECT *, OGR_STYLE FROM entities WHERE LAYER = "{layerName}"' '{outputTemplate}-points-data.csv' '{sourceFile}' -nlt POINT 2>/dev/null;
ogr2ogr -f CSV '{outputTemplate}-points-orig.csv' '{outputTemplate}-points.shp';
{basePath}/fixlabels.py '{outputTemplate}-points-orig.csv' '{outputTemplate}-points-data.csv' '{outputTemplate}-points-fixed.csv';
ogr2ogr '{outputTemplate}-points-fixed.shp' '{outputTemplate}-points-fixed.csv' 2>/dev/null;
cp '{outputTemplate}-points-fixed.dbf' '{outputTemplate}-points.dbf'
""".format(**variables))
    return output

def runCommands(commands):
    processes = {}
    while len(commands) > 0 or len(processes) > 0:
        if len(commands) > 0 and len(processes) < config.threads:
            process = subprocess.Popen(commands[0], shell = True)
            del commands[0]
            processes[process.pid] = process
        if len(commands) == 0 or len(processes) >= config.threads:
            (pid, status) = os.wait()
            if pid in processes:
                del processes[pid]


def opaque(layer):
    for input in layer["input"]:
        if 'fill' in input:
            return True
    return False


def parse_layer_config(filename, source_layer, layer_config):
    mapLayer = sanitize(source_layer)
    layer = {
        'source': filename,
        'description': source_layer,
    }
    if 'color' in layer_config:
        layer['type'] = 'line'
        layer['name'] = mapLayer + "-lines"
        layer['color'] = layer_config['color']
        layer['width'] = layer_config['width']
    elif 'fill' in layer_config:
        layer['type'] = 'area'
        layer['name'] = mapLayer + "-areas"
        layer['color'] = layer_config['fill']
    elif 'text' in layer_config:
        layer['type'] = 'point'
        layer['name'] = mapLayer + "-points"
        layer['color'] = layer_config['text']
        layer['size'] = layer_config['fontSize'] if 'fontSize' in layer_config else None
    else:
        raise Exception("Unrecognised layer config for layer %s" % layer_config)
    return layer
