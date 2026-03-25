// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Scripting.Calculator;

namespace Kotor.NET.Scripting
{
    public class NSSCompiler
    {
        public NSSCompiler()
        {

        }

        public void Compile(string source)
        {
            var parser = new CalculatorParser();
            parser.Parse(source);
        }
    }
}
