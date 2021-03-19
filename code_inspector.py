import ast
import sys
import json
import os
from os import listdir
from os.path import isfile, join
import tokenize
from pprint import pprint
from cdmcfparser import getControlFlowFromFile
from staticfg import builder
import argparse

### Path to store the results
outputPath="OutputDir"
FLAG_PNG=0
###

class Code_Inspection:
    def __init__(self,path, outCfPath, outJsonPath, format="png"):
        self.path = path
        self.outJsonPath = outJsonPath
        self.outCfPath = outCfPath
        self.fileInfo = self.inspect_file() 
        self.controlFlowInfo = self.inspect_controlflow(format)
        self.tree = self.parser_file()
        self.funcsInfo = self.inspect_functions()
        self.classesInfo = self.inspect_classes()
        self.depInfo = self.inspect_dependencies()
        self.fileJson = self.file_json()


    def parser_file(self):
        with tokenize.open(self.path) as f:
            return ast.parse(f.read(), filename=self.path)

    def inspect_file(self):
        fileInfo={}
        fileInfo["path"]=self.path
        fileName = os.path.basename(self.path).split(".")
        fileInfo["fileNameBase"]=fileName[0]
        fileInfo["extension"]=fileName[1]
        return fileInfo

    def inspect_controlflow(self,format):
        controlInfo={}
        cfg = getControlFlowFromFile(self.path)
        cfg_txt=self._formatFlow(str(cfg))
        cfg_txt_file=self.outCfPath+"/"+ self.fileInfo["fileNameBase"] + ".txt" 
        
        with open(cfg_txt_file, 'w') as outfile:
           outfile.write(cfg_txt)
        controlInfo["cfg"]= cfg_txt_file
        #print("---> %s" % self.path)

        if FLAG_PNG:
            cfg_visual = builder.CFGBuilder().build_from_file(self.fileInfo["fileNameBase"], self.path)
            cfg_path=self.outCfPath+"/"+ self.fileInfo["fileNameBase"]
            cfg_visual.build_visual(cfg_path, format=format, calls=False, show=False)
            controlInfo["png"]=cfg_path+"."+ format
            #delete the second file generated by the cfg_visual (not needed!)
            os.remove(cfg_path)
        else:
            controlInfo["png"]="None"
        return controlInfo
    
    def inspect_functions(self):
        functions_definitions = [node for node in self.tree.body if isinstance(node, ast.FunctionDef)]
        return self._f_definitions(functions_definitions)

    def inspect_classes(self):
        classes_definitions = [node for node in self.tree.body if isinstance(node, ast.ClassDef)]
        classesInfo={}
        for c in classes_definitions:
            classesInfo[c.name]={}
            classesInfo[c.name]["doc"]=ast.get_docstring(c)
            try:
                classesInfo[c.name]["extend"]=[b.id for b in c.bases]
            except:
                classesInfo[c.name]["extend"]=[b.value.func.id if isinstance(b,ast.Call) and hasattr(b, 'value') else b.value.id if hasattr(b, 'value') else "" for b in c.bases]
            classesInfo[c.name]["min_max_lineno"] = self._compute_interval(c)
            methods_definitions=[node for node in c.body if isinstance(node, ast.FunctionDef)]
            classesInfo[c.name]["methods"]=self._f_definitions(methods_definitions)
        return classesInfo

    def inspect_dependencies(self):
        depInfo={}
        for node in ast.iter_child_nodes(self.tree):
            if isinstance(node, ast.Import):
                module = []
            elif isinstance(node, ast.ImportFrom):  
                module = node.module.split('.')
            else:
                continue
            for num, n in enumerate(node.names):
                d_name="dep_"+str(num)
                depInfo[d_name]={}
                depInfo[d_name]["module"] = module
                depInfo[d_name]["name"] = n.name.split('.')
                depInfo[d_name]["alias"] = n.asname

        return depInfo 


    def file_json(self):
        FileDict={}
        FileDict["file"]=self.fileInfo
        FileDict["dependencies"]=self.depInfo
        FileDict["classes"]=self.classesInfo
        FileDict["functions"]=self.funcsInfo
        FileDict["controlflow"]=self.controlFlowInfo

        json_file=self.outJsonPath+"/" +self.fileInfo["fileNameBase"] + ".json" 
        with open(json_file, 'w') as outfile:
           json.dump(FileDict, outfile)
        return FileDict 
   

    def _f_definitions(self, functions_definitions):
        funcsInfo={}
        for f in functions_definitions:
            funcsInfo[f.name]={}
            funcsInfo[f.name]["doc"]=ast.get_docstring(f)
            funcsInfo[f.name]["args"]=[a.arg for a in f.args.args]
            rs = [ node for node in ast.walk(f) if isinstance(node, (ast.Return, ))]
            funcsInfo[f.name]["returns"] = [self._get_ids(r.value) for r in rs]
            funcsInfo[f.name]["min_max_lineno"] = self._compute_interval(f)
        return funcsInfo

    def _get_ids(self,elt):
        """Extract identifiers if present. If not return None"""
        if isinstance(elt, (ast.List, )) or isinstance(elt, (ast.Tuple, )):
            # For tuple or list get id of each item if item is a Name
            return [x.id for x in elt.elts if isinstance(x, (ast.Name, ))]
        if isinstance(elt, (ast.Name, )):
            return [elt.id]

    def _compute_interval(self, node):
        min_lineno = node.lineno
        max_lineno = node.lineno
        for node in ast.walk(node):
            if hasattr(node, "lineno"):
                min_lineno = min(min_lineno, node.lineno)
                max_lineno = max(max_lineno, node.lineno)
        return (min_lineno, max_lineno + 1)

    def _formatFlow(self, s):
        """Reformats the control flow output"""
        result = ""
        shifts = []     # positions of opening '<'
        pos = 0         # symbol position in a line
        nextIsList = False

        def IsNextList(index, maxIndex, buf):
            if index == maxIndex:
                return False
            if buf[index + 1] == '<':
                return True
            if index < maxIndex - 1:
                if buf[index + 1] == '\n' and buf[index + 2] == '<':
                    return True
            return False
  
        maxIndex = len(s) - 1
        for index in range(len(s)):
            sym = s[index]
            if sym == "\n":
                lastShift = shifts[-1]
                result += sym + lastShift * " "
                pos = lastShift
                if index < maxIndex:
                    if s[index + 1] not in "<>":
                        result += " "
                        pos += 1
                continue
            if sym == "<":
                if nextIsList == False:
                    shifts.append(pos)
                else:
                    nextIsList = False
                pos += 1
                result += sym
                continue
            if sym == ">":
                shift = shifts[-1]
                result += '\n'
                result += shift * " "
                pos = shift
                result += sym
                pos += 1
                if IsNextList(index, maxIndex, s):
                    nextIsList = True
                else:
                    del shifts[-1]
                    nextIsList = False
                continue
            result += sym
            pos += 1
        return result


def create_ouput_dirs(outputDir):

       controlFlowDir=outputDir+"/ControlFlow"

       if not os.path.exists(controlFlowDir):
           print("Creating cf %s" % controlFlowDir)
           os.makedirs(controlFlowDir)
       else:
           pass
       jsonDir= outputDir+"/JsonFiles"

       if not os.path.exists(jsonDir):
           print("Creating jsDir:%s" %jsonDir)
           os.makedirs(jsonDir)
       else:
           pass
       return controlFlowDir, jsonDir
        


def main(args=None):

    if len(sys.argv) < 2:
        print('You need to specify the file to inspect')
        sys.exit()

    input_path = sys.argv[1]

    if (not os.path.isfile(input_path)) and (not os.path.isdir(input_path)):
        print('The file or directory specified does not exist')
        sys.exit()

    if os.path.isfile(input_path):
        cfDir, jsonDir=create_ouput_dirs(outputPath)
        code_info=Code_Inspection(input_path,cfDir, jsonDir)

    else:
       dirInfo={}
       for subdir, dirs, files in os.walk(input_path):
           dirs[:] = [d for d in dirs if not d.startswith('.')]
           dirs[:] = [d for d in dirs if not d.startswith('__')]
           files = [f for f in files if not f.startswith('.')]
           files = [f for f in files if not f.startswith('__')]
           for f in files:
               if ".py" in f: 
                   path=os.path.join(subdir, f)
                   outputDir=outputPath+"/"+os.path.basename(subdir)
                   cfDir, jsonDir=create_ouput_dirs(outputDir)
                   code_info=Code_Inspection(path,cfDir, jsonDir)
                   dirInfo[outputDir]=code_info.fileJson

       json_file=outputPath + "/DirectoryInfo.json" 
       with open(json_file, 'w') as outfile:
           json.dump(dirInfo, outfile)


if __name__ == "__main__":
    main()
